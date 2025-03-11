import json
from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_certificatemanager as acm,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_s3_deployment as s3_deployment,
    aws_ssm as ssm,
    custom_resources as cr,
    Duration,
    RemovalPolicy,
    CfnOutput,
    Fn
)
from aws_cdk.aws_cloudfront_origins import S3Origin
from constructs import Construct


class FrontendStack(Stack):
    """
    Stack for deploying and configuring a static website with CloudFront distribution,
    Route53 domain configuration, and runtime configuration injection.
    """

    def __init__(
            self,
            scope: Construct,
            id: str,
            domain_name: str,
            certificate_arn: str,
            project_name: str,
            api_gateway_url: str = None,
            **kwargs
    ) -> None:
        """
        Initialize the Frontend Stack.

        Args:
            scope: The parent construct
            id: The construct id
            domain_name: The domain name for the website
            certificate_arn: The ARN of an existing ACM certificate
            project_name: Name prefix for all resources
            api_gateway_url: Optional API Gateway URL for backend integration
            **kwargs: Additional arguments to pass to the parent Stack
        """
        super().__init__(scope, id, **kwargs)

        # Create infrastructure components
        logging_bucket = self._create_logging_bucket(project_name)
        website_bucket = self._create_website_bucket(project_name, logging_bucket)
        origin_identity = self._configure_bucket_access(website_bucket, project_name)
        certificate = self._import_certificate(certificate_arn, project_name)

        # Configure API behaviors if API Gateway URL is provided
        api_behaviors = self._configure_api_behaviors(api_gateway_url) if api_gateway_url else {}

        # Create CloudFront distribution
        distribution = self._create_cloudfront_distribution(
            project_name,
            website_bucket,
            origin_identity,
            certificate,
            domain_name,
            logging_bucket,
            api_behaviors
        )

        # Configure DNS
        self._configure_dns(project_name, domain_name, distribution)

        # Deploy website content
        deployment = self._deploy_website_content(project_name, website_bucket, distribution)

        # Write runtime configuration
        self._write_runtime_config(project_name, website_bucket, deployment)

        # Output resources
        self._create_outputs(project_name, domain_name, logging_bucket)

    def _create_logging_bucket(self, project_name: str) -> s3.Bucket:
        """Create S3 bucket for access logs."""
        return s3.Bucket(
            self,
            f"{project_name}-LoggingBucket",
            bucket_name=f"{project_name}-website-logs".lower(),
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(expiration=Duration.days(90))
            ]
        )

    def _create_website_bucket(self, project_name: str, logging_bucket: s3.Bucket) -> s3.Bucket:
        """Create S3 bucket for website content with logging enabled."""
        return s3.Bucket(
            self,
            f"{project_name}-WebsiteBucket",
            bucket_name=f"{project_name}-website".lower(),
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            server_access_logs_bucket=logging_bucket,
            server_access_logs_prefix="website-bucket-logs/",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

    def _configure_bucket_access(self, website_bucket: s3.Bucket, project_name: str) -> cloudfront.OriginAccessIdentity:
        """Configure CloudFront access to the website bucket."""
        # Create Origin Access Identity
        oai = cloudfront.OriginAccessIdentity(self, f"{project_name}-OAI")

        # Grant read access to CloudFront
        website_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[website_bucket.arn_for_objects("*")],
                principals=[iam.CanonicalUserPrincipal(
                    oai.cloud_front_origin_access_identity_s3_canonical_user_id
                )],
            )
        )

        return oai

    def _import_certificate(self, certificate_arn: str, project_name: str) -> acm.ICertificate:
        """Import existing ACM certificate."""
        return acm.Certificate.from_certificate_arn(
            self,
            f"{project_name}-SiteCertificate",
            certificate_arn
        )

    def _configure_api_behaviors(self, api_gateway_url: str) -> dict:
        """Configure CloudFront behaviors for API Gateway integration."""
        # Remove protocol and trailing slash
        trimmed = api_gateway_url.rstrip("/")
        if trimmed.startswith("https://"):
            trimmed = trimmed[len("https://"):]

        # Split into domain and stage (if any)
        parts = trimmed.split("/", 1)
        api_gateway_host = parts[0]

        # Ensure stage path is properly formatted
        api_origin_path = "/" + parts[1].rstrip("/") if len(parts) > 1 else ""

        # Create HTTP origin for API Gateway
        api_origin = origins.HttpOrigin(
            domain_name=api_gateway_host,
            origin_path=api_origin_path,
        )

        # Return behavior configuration
        return {
            "api/*": cloudfront.BehaviorOptions(
                origin=api_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            )
        }

    def _create_cloudfront_distribution(
            self,
            project_name: str,
            website_bucket: s3.Bucket,
            oai: cloudfront.OriginAccessIdentity,
            certificate: acm.ICertificate,
            domain_name: str,
            logging_bucket: s3.Bucket,
            additional_behaviors: dict
    ) -> cloudfront.Distribution:
        """Create CloudFront distribution for the website."""
        # Using the original S3Origin which is deprecated but works
        return cloudfront.Distribution(
            self,
            f"{project_name}-SiteDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=S3Origin(website_bucket, origin_access_identity=oai),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            additional_behaviors=additional_behaviors,
            domain_names=[domain_name],
            certificate=certificate,
            default_root_object="index.html",
            enable_logging=True,
            log_bucket=logging_bucket,
            log_file_prefix="cloudfront-logs/",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html"
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html"
                )
            ]
        )

    def _configure_dns(
            self,
            project_name: str,
            domain_name: str,
            distribution: cloudfront.Distribution
    ) -> None:
        """Configure Route53 DNS records."""
        # Look up the hosted zone
        zone = route53.HostedZone.from_lookup(
            self,
            f"{project_name}-HostedZone",
            domain_name=domain_name
        )

        # Create A record pointing to CloudFront
        route53.ARecord(
            self,
            f"{project_name}-SiteAliasRecord",
            zone=zone,
            record_name=domain_name,
            target=route53.RecordTarget.from_alias(
                targets.CloudFrontTarget(distribution)
            )
        )

    def _deploy_website_content(
            self,
            project_name: str,
            website_bucket: s3.Bucket,
            distribution: cloudfront.Distribution
    ) -> s3_deployment.BucketDeployment:
        """Deploy website content to S3 bucket."""
        return s3_deployment.BucketDeployment(
            self,
            f"{project_name}-DeployWebsite",
            sources=[s3_deployment.Source.asset("../frontend/build")],
            destination_bucket=website_bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

    def _write_runtime_config(
            self,
            project_name: str,
            website_bucket: s3.Bucket,
            deployment: s3_deployment.BucketDeployment
    ) -> None:
        """
        Fetch runtime config from SSM at deploy time (not synth),
        then write config.json to the website bucket using a Custom Resource.
        """

        # 1) Fetch all SSM parameters at deploy time
        fetch_params = cr.AwsCustomResource(
            self,
            f"{project_name}-FetchParams",
            on_create=cr.AwsSdkCall(
                service="SSM",
                action="getParameters",
                parameters={
                    "Names": [
                        f"/{project_name}/REACT_APP_COGNITO_USER_POOL_ID",
                        f"/{project_name}/REACT_APP_COGNITO_USER_POOL_CLIENT_ID",
                        f"/{project_name}/REACT_APP_API_GATEWAY_URL"
                    ],
                    "WithDecryption": True
                },
                physical_resource_id=cr.PhysicalResourceId.of(f"{project_name}-FetchParams-v1")
            ),
            on_update=cr.AwsSdkCall(
                # use the same call on update, so you get fresh parameter values if they change
                service="SSM",
                action="getParameters",
                parameters={
                    "Names": [
                        f"/{project_name}/REACT_APP_COGNITO_USER_POOL_ID",
                        f"/{project_name}/REACT_APP_COGNITO_USER_POOL_CLIENT_ID",
                        f"/{project_name}/REACT_APP_API_GATEWAY_URL"
                    ],
                    "WithDecryption": True
                },
                physical_resource_id=cr.PhysicalResourceId.of(f"{project_name}-FetchParams-v1")
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["ssm:GetParameters"],
                    resources=[
                        # Restrict to your project’s SSM path
                        f"arn:aws:ssm:{self.region}:{self.account}:parameter/{project_name}/*"
                    ]
                )
            ])
        )

        # Each parameter will appear under "Parameters" in the API response array
        # in the same order you requested them. Example response:
        # {
        #   "Parameters": [
        #       { "Name": "/PROJECT/REACT_APP_COGNITO_USER_POOL_ID", "Value": "XXXXXX" },
        #       { "Name": "/PROJECT/REACT_APP_COGNITO_USER_POOL_CLIENT_ID", "Value": "YYYYYY" },
        #       { "Name": "/PROJECT/REACT_APP_API_GATEWAY_URL", "Value": "ZZZZZZ" }
        #   ],
        #   "InvalidParameters": []
        # }

        user_pool_id = fetch_params.get_response_field("Parameters.0.Value")
        user_pool_client_id = fetch_params.get_response_field("Parameters.1.Value")
        api_gateway_url = fetch_params.get_response_field("Parameters.2.Value")

        # 2) Write the config.json file to S3 in a second Custom Resource
        write_config = cr.AwsCustomResource(
            self,
            f"{project_name}-WriteConfig",
            on_create=cr.AwsSdkCall(
                service="S3",
                action="putObject",
                parameters={
                    "Bucket": website_bucket.bucket_name,
                    "Key": "config.json",
                    # Build the JSON body from the SSM parameter tokens
                    "Body": Fn.join(
                        "",
                        [
                            "{",
                            f"\"REACT_APP_COGNITO_USER_POOL_ID\":\"", user_pool_id, "\",",
                            f"\"REACT_APP_COGNITO_USER_POOL_CLIENT_ID\":\"", user_pool_client_id, "\",",
                            f"\"REACT_APP_API_GATEWAY_URL\":\"", api_gateway_url, "\"",
                            "}"
                        ]
                    ),
                    "ContentType": "application/json"
                },
                physical_resource_id=cr.PhysicalResourceId.of("config.json")  # ensures stable resource ID
            ),
            on_update=cr.AwsSdkCall(
                service="S3",
                action="putObject",
                parameters={
                    "Bucket": website_bucket.bucket_name,
                    "Key": "config.json",
                    "Body": Fn.join(
                        "",
                        [
                            "{",
                            f"\"REACT_APP_COGNITO_USER_POOL_ID\":\"", user_pool_id, "\",",
                            f"\"REACT_APP_COGNITO_USER_POOL_CLIENT_ID\":\"", user_pool_client_id, "\",",
                            f"\"REACT_APP_API_GATEWAY_URL\":\"", api_gateway_url, "\"",
                            "}"
                        ]
                    ),
                    "ContentType": "application/json"
                },
                physical_resource_id=cr.PhysicalResourceId.of("config.json")
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["s3:PutObject"],
                    resources=[website_bucket.arn_for_objects("config.json")]
                )
            ])
        )

        # Enforce the correct order: we must fetch parameters before writing config.json
        # and we must have the website bucket + initial deployment in place before writing config.
        write_config.node.add_dependency(fetch_params)
        write_config.node.add_dependency(website_bucket)
        write_config.node.add_dependency(deployment)

    def _create_outputs(self, project_name: str, domain_name: str, logging_bucket: s3.Bucket) -> None:
        """Create CloudFormation outputs."""
        CfnOutput(
            self,
            f"{project_name}-WebsiteUrl",
            value=f"https://{domain_name}",
            description="The URL of the deployed website."
        )

        CfnOutput(
            self,
            f"{project_name}-LoggingBucketName",
            value=logging_bucket.bucket_name,
            description="The S3 bucket containing access logs."
        )

        CfnOutput(
            self,
            f"{project_name}-CloudFrontLogsPath",
            value=f"s3://{logging_bucket.bucket_name}/cloudfront-logs/",
            description="Path to CloudFront access logs."
        )