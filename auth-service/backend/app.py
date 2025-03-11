import os
from aws_cdk import App, Environment
from cdk_stacks.frontend_stack import FrontendStack
from cdk_stacks.auth_stack import AuthStack
from cdk_stacks.api_stack import ApiStack

def main() -> None:
    """
    Deploys the CDK stacks with defined dependencies.

    This script expects the following keys in cdk.json under 'context':
      - awsRegion: The AWS region for deployment.
      - projectName: A unique project identifier for resource naming.
      - domainName: The domain name for the Frontend stack.
      - certificateArn: The ARN of the ACM certificate for the Frontend stack.
      - account: The AWS account ID.

    Raises:
        ValueError: If any required context key is not set in cdk.json.
    """
    app = App()

    # --------------------------------------------------------------------------
    # Retrieve Context Values
    # --------------------------------------------------------------------------
    project_name = app.node.try_get_context("projectName")
    if not project_name:
        raise ValueError("Must set 'projectName' in cdk.json under 'context.projectName'")

    region = app.node.try_get_context("awsRegion")
    if not region:
        raise ValueError("Must set 'awsRegion' in cdk.json under 'context.awsRegion'")

    domain_name = app.node.try_get_context("domainName")
    if not domain_name:
        raise ValueError("Must set 'domainName' in cdk.json under 'context.domainName'")

    certificate_arn = app.node.try_get_context("certificateArn")
    if not certificate_arn:
        raise ValueError("Must set 'certificateArn' in cdk.json under 'context.certificateArn'")

    account = app.node.try_get_context("account")
    if not account:
        raise ValueError("Must set 'account' in cdk.json under 'context.account'")

    env = Environment(account=account, region=region)

    # --------------------------------------------------------------------------
    # 1) Deploy the Auth Stack
    # --------------------------------------------------------------------------
    auth_stack = AuthStack(
        app,
        f"{project_name}-AuthStack",
        env=env,
        project_name=project_name,
    )

    # --------------------------------------------------------------------------
    # 2) Deploy the API Stack
    # --------------------------------------------------------------------------
    api_stack = ApiStack(
        app,
        f"{project_name}-ApiStack",
        user_pool_id=auth_stack.user_pool_id,
        user_pool_client_id=auth_stack.user_pool_client_id,
        env=env,
        project_name=project_name,
    )
    api_stack.add_dependency(auth_stack)

    # --------------------------------------------------------------------------
    # 3) Deploy the Frontend Stack with API Gateway as the backend
    # --------------------------------------------------------------------------
    frontend_stack = FrontendStack(
        app,
        f"{project_name}-FrontendStack",
        domain_name=domain_name,
        certificate_arn=certificate_arn,
        project_name=project_name,
        api_gateway_url=api_stack.api.url,
        env=env,
    )
    frontend_stack.add_dependency(api_stack)

    app.synth()

if __name__ == "__main__":
    main()
