from aws_cdk import (
    Stack,
    CfnOutput,
    aws_apigateway as apigateway,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_verifiedpermissions as vp,
    aws_logs as logs,
    aws_ssm as ssm,
    Duration,
    RemovalPolicy,
)
from pathlib import Path
from constructs import Construct
from typing import Dict, Optional


class ApiStack(Stack):
    """
    A CDK stack that creates:
      1) Verified Permissions policy store (with a Cedar schema and a Cedar policy).
      2) Two Lambda functions (a /hello endpoint and a custom authorizer).
      3) An API Gateway with a Lambda token authorizer, CORS, and integration.
      4) A CloudFormation output with the API Gateway URL.
    """

    def __init__(
            self,
            scope: Construct,
            id: str,
            user_pool_id: str,
            user_pool_client_id: str,
            project_name: str,
            **kwargs,
    ) -> None:
        """
        Initialize the ApiStack.

        Args:
            scope: The parent construct
            id: The construct id
            user_pool_id: The Cognito User Pool ID for authentication
            user_pool_client_id: The Cognito User Pool Client ID
            project_name: Name prefix for all resources
            **kwargs: Additional arguments to pass to the parent Stack
        """
        super().__init__(scope, id, **kwargs)
        self.project_name = project_name

        # Create Verified Permissions resources
        self.policy_store = self._create_policy_store()
        self._setup_admin_policy()

        # Create Lambda functions
        hello_lambda = self._create_lambda_function(
            "HelloFunction",
            "hello",
            user_pool_id,
            user_pool_client_id,
            timeout=Duration.seconds(420),
        )

        authorizer_lambda = self._create_lambda_function(
            "LambdaAuthorizer",
            "authorizer",
            user_pool_id,
            user_pool_client_id,
        )

        # Grant permissions for Verified Permissions access
        self._grant_verified_permissions_access(
            authorizer_lambda,
            self.policy_store.attr_policy_store_id
        )

        # Create API Gateway and configure resources
        self.api = self._create_api_gateway()
        authorizer = self._create_token_authorizer(authorizer_lambda)
        self._create_hello_resource(self.api, hello_lambda, authorizer)

        # Create outputs and parameters
        self._create_api_output()

    def _setup_admin_policy(self) -> None:
        """
        Load and create the admin Cedar policy in the policy store.
        """
        admin_cedar = self._load_cedar_policy("admin_policy.cedar")
        self._create_admin_policy(admin_cedar, self.policy_store.attr_policy_store_id)

    def _load_cedar_schema(self, filename: str) -> str:
        """
        Load a Cedar schema file from the 'cedar' directory.

        Args:
            filename: The name of the schema file to load

        Returns:
            str: The content of the Cedar schema file
        """
        cedar_dir = (Path(__file__).resolve().parent / ".." / "cedar").resolve()
        schema_path = cedar_dir / filename
        return schema_path.read_text(encoding="utf-8")

    def _load_cedar_policy(self, policy_filename: str) -> str:
        """
        Load a Cedar policy file from the 'cedar' directory.

        Args:
            policy_filename: The name of the policy file to load

        Returns:
            str: The content of the Cedar policy file
        """
        cedar_dir = (Path(__file__).resolve().parent / ".." / "cedar").resolve()
        policy_path = cedar_dir / policy_filename
        return policy_path.read_text(encoding="utf-8")

    def _create_policy_store(self) -> vp.CfnPolicyStore:
        """
        Create a Verified Permissions policy store with validation enabled
        using a Cedar schema.

        Returns:
            vp.CfnPolicyStore: The created policy store
        """
        cedar_schema = self._load_cedar_schema("schema.json")

        return vp.CfnPolicyStore(
            self,
            f"{self.project_name}-PolicyStore",
            validation_settings=vp.CfnPolicyStore.ValidationSettingsProperty(
                mode="STRICT"
            ),
            description=f"{self.project_name}-PolicyStore",
            schema=vp.CfnPolicyStore.SchemaDefinitionProperty(
                cedar_json=cedar_schema
            )
        )

    def _create_admin_policy(self, cedar_policy: str, policy_store_id: str) -> vp.CfnPolicy:
        """
        Create a policy in the Verified Permissions policy store using the
        provided Cedar policy.

        Args:
            cedar_policy: The Cedar policy content as a string
            policy_store_id: The ID of the policy store

        Returns:
            vp.CfnPolicy: The created policy
        """
        admin_policy = vp.CfnPolicy(
            self,
            f"{self.project_name}-AdminPolicy",
            policy_store_id=policy_store_id,
            definition=vp.CfnPolicy.PolicyDefinitionProperty(
                static=vp.CfnPolicy.StaticPolicyDefinitionProperty(
                    description="Grants Admin-level access",
                    statement=cedar_policy,
                )
            ),
        )
        admin_policy.node.add_dependency(self.policy_store)
        return admin_policy

    def _grant_verified_permissions_access(
            self, lambda_fn: _lambda.Function, policy_store_id: str
    ) -> None:
        """
        Grant the specified Lambda function permission to call Verified
        Permissions' IsAuthorized API.

        Args:
            lambda_fn: The Lambda function to grant permissions to
            policy_store_id: The ID of the policy store
        """
        policy_store_arn = (
            f"arn:aws:verifiedpermissions::{self.account}:policy-store/{policy_store_id}"
        )
        lambda_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["verifiedpermissions:IsAuthorized"],
                resources=[policy_store_arn],
            )
        )

    def _create_lambda_function(
            self,
            name: str,
            filename: str,
            user_pool_id: str,
            user_pool_client_id: str,
            timeout: Duration = Duration.seconds(3),
            extra_env: Optional[Dict[str, str]] = None,
    ) -> _lambda.Function:
        """
        Create a Lambda function with environment variables set.

        Args:
            name: The name of the Lambda function
            filename: The filename containing the Lambda handler
            user_pool_id: The Cognito User Pool ID
            user_pool_client_id: The Cognito User Pool Client ID
            timeout: The Lambda execution timeout
            extra_env: Additional environment variables to set

        Returns:
            _lambda.Function: The created Lambda function
        """
        env_vars = {
            "USER_POOL_ID": user_pool_id,
            "CLIENT_ID": user_pool_client_id,
            "POLICY_STORE_ID": self.policy_store.attr_policy_store_id,
        }

        # Add any extra environment variables
        if extra_env:
            env_vars.update(extra_env)

        fn = _lambda.Function(
            self,
            f"{self.project_name}-{name}",
            function_name=f"{self.project_name}-{name}",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler=f"{filename}.lambda_handler",
            code=_lambda.Code.from_asset(
                f"lambda/{filename}",
                bundling=self._get_bundling_options()
            ),
            environment=env_vars,
            timeout=timeout,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )
        return fn

    def _get_bundling_options(self) -> Dict:
        """
        Get bundling options for Lambda functions.

        Returns:
            Dict: The bundling options configuration
        """
        return {
            "image": _lambda.Runtime.PYTHON_3_9.bundling_image,
            "command": [
                "bash",
                "-c",
                (
                    "pip install --no-cache-dir -r requirements.txt -t /asset-output "
                    "&& cp -au . /asset-output"
                ),
            ],
        }

    def _create_api_gateway(self) -> apigateway.RestApi:
        """
        Create an API Gateway REST API with a 'prod' stage and comprehensive
        logging configuration.

        Returns:
            apigateway.RestApi: The created API Gateway
        """
        access_log_group = self._create_access_log_group()

        return apigateway.RestApi(
            self,
            f"{self.project_name}-ApiGateway",
            rest_api_name=f"{self.project_name}-RestAPI",
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                access_log_destination=apigateway.LogGroupLogDestination(access_log_group),
                access_log_format=apigateway.AccessLogFormat.json_with_standard_fields(
                    caller=True,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True,
                ),
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True,
            ),
        )

    def _create_access_log_group(self) -> logs.LogGroup:
        """
        Create a CloudWatch log group for API Gateway access logs.

        Returns:
            logs.LogGroup: The created log group
        """
        return logs.LogGroup(
            self,
            f"{self.project_name}-ApiAccessLogs",
            log_group_name=f"/aws/apigateway/{self.project_name}-AccessLogs",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )

    def _create_token_authorizer(
            self, authorizer_lambda: _lambda.Function
    ) -> apigateway.TokenAuthorizer:
        """
        Create a Lambda token authorizer for the given authorizer Lambda function.

        Args:
            authorizer_lambda: The Lambda function to use as an authorizer

        Returns:
            apigateway.TokenAuthorizer: The created token authorizer
        """
        return apigateway.TokenAuthorizer(
            self,
            f"{self.project_name}-LambdaTokenAuthorizer",
            authorizer_name=f"{self.project_name}-LambdaTokenAuthorizer",
            handler=authorizer_lambda,
        )

    def _create_hello_resource(
            self,
            api: apigateway.RestApi,
            hello_lambda: _lambda.Function,
            authorizer: apigateway.IAuthorizer,
    ) -> apigateway.Resource:
        """
        Create the /hello resource on the given API with Lambda integration
        and CORS configuration.

        Args:
            api: The API Gateway to add the resource to
            hello_lambda: The Lambda function to integrate with
            authorizer: The authorizer to use for this endpoint

        Returns:
            apigateway.Resource: The created API resource
        """
        # Grant API Gateway permission to invoke the Lambda
        hello_lambda.grant_invoke(iam.ServicePrincipal("apigateway.amazonaws.com"))

        # Create the resource
        hello_resource = api.root.add_resource("hello")

        # Add method with Lambda integration and authorizer
        hello_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(hello_lambda, proxy=True),
            authorization_type=apigateway.AuthorizationType.CUSTOM,
            authorizer=authorizer,
        )

        # Configure CORS
        hello_resource.add_cors_preflight(
            allow_origins=["*"],
            allow_methods=["GET", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

        return hello_resource

    def _create_api_output(self) -> None:
        """
        Create a CloudFormation output and an SSM parameter with the
        deployed API Gateway URL.
        """
        api_url = self.api.url.rstrip("/")

        # Create CloudFormation output
        CfnOutput(
            self,
            f"{self.project_name}-ApiGatewayUrl",
            value=api_url,
            description="The URL of the API Gateway endpoint.",
        )

        # Create SSM parameter for frontend configuration
        ssm.StringParameter(
            self,
            f"{self.project_name}-ApiGatewayUrlParameter",
            parameter_name=f"/{self.project_name}/REACT_APP_API_GATEWAY_URL",
            string_value=api_url,
            description="The API Gateway URL for the frontend configuration",
        )