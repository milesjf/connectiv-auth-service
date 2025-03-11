# ConnectiV Authentication Service

The **Auth Service** is a full-stack authentication and authorization system built with **AWS CDK (Python) for backend infrastructure** and a **React-based frontend**. It provides secure API access using **Amazon Cognito, API Gateway, AWS Lambda**, and **AWS Verified Permissions (Cedar policy store)** for fine-grained authorization.

## Overview

- **Backend (AWS CDK & Lambda)**
  - API Gateway with Lambda functions for authentication and authorization.
  - Custom Lambda authorizer that validates Cognito JWT tokens.
  - **AWS Verified Permissions** (Cedar policy store) for role-based access control (RBAC).
  - Infrastructure-as-code deployment using AWS CDK (Python).
  - Automated frontend deployment with S3 and CloudFront integration.
  - Configuration management through AWS Parameter Store.

- **Frontend (React)**
  - User authentication UI.
  - Secure API interactions using authorization tokens.
  - Runtime configuration loaded from server for easy deployment without rebuilds.

## Project Structure

```
auth-service/
├── backend/      # AWS CDK-based backend infrastructure
│   ├── cdk_stacks/   # CDK stack definitions
│   │   ├── api_stack.py     # API Gateway & Lambda integration
│   │   ├── auth_stack.py    # Cognito User Pool & App Client
│   │   └── frontend_stack.py # Frontend deployment with S3 and CloudFront
│   ├── lambda/       # Lambda functions (Authorizer, Hello World, etc.)
│   ├── policy_store/ # AWS Verified Permissions (Cedar policy-based authorization)
│   ├── app.py        # CDK app entry point
│   └── README.md     # Backend-specific documentation
├── frontend/     # React-based frontend application
│   ├── public/       # Static assets
│   ├── src/          # Frontend source code
│   ├── package.json  # Frontend dependencies
│   └── README.md     # Frontend-specific documentation
```

## Getting Started

Each component has its own `README.md` with setup and deployment instructions:

- **Backend:** See [`backend/README.md`](backend/README.md) for CDK deployment and AWS Verified Permissions setup.
- **Frontend:** See [`frontend/README.md`](frontend/README.md) for UI development and authentication integration.

## Deployment

The entire stack can be deployed through a single AWS CDK command:

```bash
cd backend
cdk deploy --all
```

This will:
1. Set up the authentication infrastructure (Cognito, API Gateway, Lambda)
2. Deploy the frontend to S3 with CloudFront distribution
3. Configure all necessary parameters and DNS settings

For individual component deployment or more detailed instructions, see the component-specific README files.

## Configuration

The application uses AWS Parameter Store to manage configuration between the backend and frontend:

- Configuration values are stored in AWS Parameter Store
- During deployment, the CDK stack retrieves these values
- A `config.json` file is automatically generated and deployed to the frontend S3 bucket
- The React application loads this configuration at runtime

This approach eliminates the need for environment-specific builds and simplifies deployment across different environments.