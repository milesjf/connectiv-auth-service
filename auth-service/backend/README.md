# Backend - Auth Service

This backend is built using **AWS CDK (Python)** and provides authentication and authorization via **Amazon Cognito, API Gateway, AWS Lambda**, and **AWS Verified Permissions (Cedar policy store)**.

## Features

- **Authentication** – Amazon Cognito manages user authentication.
- **Authorization** – AWS Verified Permissions with Cedar policy store controls fine-grained access.
- **API Gateway & Lambda** – A secured API with a custom Lambda authorizer.
- **Infrastructure as Code** – AWS CDK manages and deploys all resources.
- **Runtime Configuration** – Stores configuration in AWS Parameter Store for frontend integration.

## Project Structure

```
backend/
├── cdk_stacks/                # CDK stack definitions
│   ├── api_stack.py           # API Gateway & Lambda integration
│   ├── auth_stack.py          # Cognito User Pool & App Client
│   ├── frontend_stack.py      # Frontend deployment with S3 and CloudFront
├── lambda/                    # Lambda functions
│   ├── authorizer/            # Custom authorizer (Cognito JWT validation)
│   ├── hello/                 # Example API Lambda function
├── policy_store/              # AWS Verified Permissions (Cedar policies)
│   ├── admin_policy.cedar     # Example policy definition
├── app.py                     # CDK application entry point
├── cdk.json                   # CDK configuration
├── requirements.txt           # Backend dependencies
└── README.md                  # This file
```

## Prerequisites

- **Node.js & npm** (Required for AWS CDK)
  ```bash
  nvm install --lts  # Recommended way (using Node Version Manager)
  ```
- **AWS CDK v2+**
  ```bash
  npm install -g aws-cdk
  ```
- **Python 3.9+**
- **Docker** (Required for bundling Lambda dependencies)
- **AWS CLI** (Configured with necessary credentials)

## Setup

1. **Install Node.js & npm**
   ```bash
   nvm install --lts  # or install from https://nodejs.org/
   ```
2. **Install AWS CDK**
   ```bash
   npm install -g aws-cdk
   ```
3. **Create a Virtual Environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # macOS/Linux
   .venv\Scripts\activate.bat # Windows
   ```  
4. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```
5. **Set Required Parameters in AWS Parameter Store**
   The following parameters need to be created in AWS Parameter Store:
    - `/{project_name}/REACT_APP_COGNITO_USER_POOL_ID`
    - `/{project_name}/REACT_APP_COGNITO_USER_POOL_CLIENT_ID`
    - `/{project_name}/REACT_APP_API_GATEWAY_URL`

   These parameters will be automatically read during CDK deployment and used to generate the frontend configuration.

6. **Deploy Backend**
   ```bash
   cdk synth && cdk deploy --all
   ```

## How It Works

- **API Gateway routes requests** to a Lambda function.
- **Cognito handles authentication** (JWT-based).
- **Custom Lambda authorizer** validates JWT tokens before API access.
- **AWS Verified Permissions (Cedar)** enforces role-based access policies.
- **Frontend Stack** deploys a React application to S3 with CloudFront distribution, automatically configuring it with SSM parameters.

## Deployment

To deploy the entire backend and frontend:
```bash
cdk deploy --all
```

For individual stacks:
```bash
cdk deploy ApiStack        # Deploy only the API stack
cdk deploy AuthStack       # Deploy only the Auth stack
cdk deploy FrontendStack   # Deploy only the Frontend stack
```

## Cleanup

To remove all AWS resources:
```bash
cdk destroy --all
```

Note: When deleting resources, you might encounter an error if the S3 bucket isn't empty. You can either:
1. Enable `auto_delete_objects=True` in the S3 bucket configuration (in `frontend_stack.py`)
2. Manually empty the bucket before deletion:
   ```bash
   aws s3 rm s3://{project-name}-website --recursive
   ```

## Next Steps

- Modify **Cedar policies** to refine access controls.
- Extend **Lambda functions** for additional API endpoints.
- Customize the **frontend** to meet specific application requirements.
- Implement additional **CloudFront security headers** for enhanced security.