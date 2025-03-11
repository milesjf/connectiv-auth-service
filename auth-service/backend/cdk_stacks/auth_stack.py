from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_cognito as cognito,
    aws_ssm as ssm,
    Environment,
)
from constructs import Construct
from typing import Dict


class AuthStack(Stack):
    """
    A CDK stack for creating a Cognito authentication setup.
    It includes:
      1) A Cognito User Pool.
      2) A hosted Cognito domain.
      3) A User Pool Client.
      4) An optional Admin group.
      5) CloudFormation outputs and SSM parameters for referencing these resources.
    """

    def __init__(
            self,
            scope: Construct,
            id: str,
            project_name: str,
            **kwargs,
    ) -> None:
        """
        Initialize the Auth Stack.

        Args:
            scope: The parent construct
            id: The construct id
            project_name: Name prefix for all resources
            **kwargs: Additional arguments to pass to the parent Stack
        """
        super().__init__(scope, id, **kwargs)
        self.project_name = project_name

        # Generate domain prefix (must be globally unique)
        domain_prefix = f"{self.project_name.lower()}-connectiv-domain"

        # Create authentication resources
        self.user_pool = self._create_user_pool()
        self.user_pool_domain = self._create_user_pool_domain(domain_prefix)
        self.user_pool_client = self._create_user_pool_client()
        self.admin_group = self._create_admin_group()

        # Create outputs and parameters
        self._create_outputs(domain_prefix)

        # Expose resources for cross-stack references
        self.user_pool_id = self.user_pool.user_pool_id
        self.user_pool_client_id = self.user_pool_client.user_pool_client_id

    def _create_user_pool(self) -> cognito.UserPool:
        """
        Create and configure the Cognito User Pool with custom attributes
        and password policies.

        Returns:
            cognito.UserPool: The created user pool
        """
        custom_attrs = self._get_custom_attributes()

        return cognito.UserPool(
            self,
            f"{self.project_name}-UserPool",
            user_pool_name=f"{self.project_name}-CognitoUserPool",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(username=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=False, phone=False),
            password_policy=cognito.PasswordPolicy(
                min_length=6,
                require_lowercase=False,
                require_uppercase=False,
                require_digits=False,
                require_symbols=False,
            ),
            custom_attributes=custom_attrs,
            removal_policy=RemovalPolicy.DESTROY,
        )

    def _create_user_pool_domain(self, domain_prefix: str) -> cognito.UserPoolDomain:
        """
        Create a hosted Cognito domain with the given prefix.

        Args:
            domain_prefix: The prefix for the Cognito domain

        Returns:
            cognito.UserPoolDomain: The created user pool domain
        """
        return self.user_pool.add_domain(
            f"{self.project_name}-UserPoolDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=domain_prefix,
            ),
        )

    def _create_user_pool_client(self) -> cognito.UserPoolClient:
        """
        Create a client for the user pool with appropriate authentication flows
        and attribute access.

        Returns:
            cognito.UserPoolClient: The created user pool client
        """
        custom_attrs = self._get_custom_attributes()
        client_attributes = cognito.ClientAttributes().with_custom_attributes(*list(custom_attrs.keys()))

        return cognito.UserPoolClient(
            self,
            f"{self.project_name}-UserPoolClient",
            user_pool_client_name=f"{self.project_name}-AppClient",
            user_pool=self.user_pool,
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                user_srp=True,
                user_password=True,
            ),
            read_attributes=client_attributes
        )

    def _create_admin_group(self) -> cognito.CfnUserPoolGroup:
        """
        Create a default Admin group in the user pool with elevated permissions.

        Returns:
            cognito.CfnUserPoolGroup: The created admin group
        """
        return cognito.CfnUserPoolGroup(
            self,
            f"{self.project_name}-AdminGroup",
            group_name="Admin",
            user_pool_id=self.user_pool.user_pool_id,
            precedence=1,
            description="Default Admin group for elevated permissions",
        )

    def _get_custom_attributes(self) -> Dict[str, cognito.ICustomAttribute]:
        """
        Define all custom attributes for the User Pool.

        Returns:
            Dict[str, cognito.ICustomAttribute]: Dictionary of custom attributes
        """
        return {
            "dataProductAccess": cognito.StringAttribute(min_len=1, max_len=256, mutable=True),
            "department": cognito.StringAttribute(min_len=1, max_len=256, mutable=True),
        }

    def _create_outputs(self, domain_prefix: str) -> None:
        """
        Create CloudFormation outputs and SSM parameters for the User Pool and Client.

        Args:
            domain_prefix: The prefix used for the Cognito domain
        """
        # Calculate the hosted UI URL
        hosted_ui_url = f"https://{domain_prefix}.auth.{self.region}.amazoncognito.com"

        # Create CloudFormation outputs
        self._create_cfn_outputs(hosted_ui_url)

        # Create SSM parameters for cross-stack references
        self._create_ssm_parameters()

    def _create_cfn_outputs(self, hosted_ui_url: str) -> None:
        """
        Create CloudFormation outputs for Cognito resources.

        Args:
            hosted_ui_url: The URL for the Cognito hosted UI
        """
        CfnOutput(
            self,
            f"{self.project_name}-UserPoolId",
            value=self.user_pool.user_pool_id,
            description="The Cognito User Pool ID.",
        )

        CfnOutput(
            self,
            f"{self.project_name}-UserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            description="The Cognito User Pool Client ID.",
        )

        CfnOutput(
            self,
            f"{self.project_name}-CognitoHostedDomain",
            value=hosted_ui_url,
            description="Use this domain for the Cognito hosted UI login pages.",
        )

    def _create_ssm_parameters(self) -> None:
        """
        Create SSM parameters for frontend configuration and cross-stack references.
        """
        ssm.StringParameter(
            self,
            f"{self.project_name}-UserPoolIdParameter",
            parameter_name=f"/{self.project_name}/REACT_APP_COGNITO_USER_POOL_ID",
            string_value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID for the frontend configuration",
        )

        ssm.StringParameter(
            self,
            f"{self.project_name}-UserPoolClientIdParameter",
            parameter_name=f"/{self.project_name}/REACT_APP_COGNITO_USER_POOL_CLIENT_ID",
            string_value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID for the frontend configuration",
        )