# Frontend - Auth Service

This is a **React-based frontend** that interacts with the **backend authentication service** built using AWS. It provides a user authentication interface and allows secure API access via **Amazon Cognito and API Gateway** for DataZone access via Leidos ConnectiV.

## Features

- **User Authentication** – Sign in using Amazon Cognito.
- **Secure API Calls** – Authenticated requests to API Gateway.
- **Token Handling** – Uses **Cognito JWT tokens** for authorization.
- **React UI** – Built with modern React.js.
- **Automated Configuration** – Configuration is automatically deployed from AWS Parameter Store during CDK deployment, no manual setup required.

## Project Structure

```
frontend/
├── public/
│   ├── index.html         # Main HTML file
│   └── favicon.ico        # Icons and static assets
├── src/
│   ├── App.js             # Main application logic
│   ├── index.js           # React entry point (fetches config.json)
│   ├── api.js             # API request logic
├── package.json           # Project metadata and dependencies
└── README.md              # This file
```

## Prerequisites

- **Node.js & npm**  
  Install Node.js and npm from [nodejs.org](https://nodejs.org/) or via your package manager.

- **AWS Credentials**  
  Ensure your AWS credentials are configured for API access.

## Setup

### 1. Install Project Dependencies

```bash
npm install
```

### 2. Configuration

#### Infrastructure Configuration

The project utilizes AWS Parameter Store for configuration settings. These parameters are automatically fetched during the CDK deployment process and written to a `config.json` file in the deployed S3 bucket.

Required parameters in AWS Parameter Store (created by the CDK stack):
- `/{project_name}/REACT_APP_COGNITO_USER_POOL_ID`
- `/{project_name}/REACT_APP_COGNITO_USER_POOL_CLIENT_ID`
- `/{project_name}/REACT_APP_API_GATEWAY_URL`

You don't need to manually create or modify the `config.json` file for production deployments, as this is handled automatically by the CDK deployment process.

### 3. Run the App in Development Mode

```bash
npm start
```

The app will be available at [http://localhost:3000](http://localhost:3000).

## How It Works

- **Runtime Configuration:**  
  At startup, `index.js` fetches `/config.json` and assigns its content to `window.appConfig`. The application then reads its Cognito and API Gateway settings from this runtime configuration.
- **User Authentication:**  
  Users log in via Amazon Cognito. The app creates a Cognito User Pool using the runtime configuration.
- **Secure API Calls:**  
  After signing in, JWT tokens are used to authenticate API requests to API Gateway.
- **Infrastructure Configuration:**
  The CDK stack automatically pulls configuration from AWS Parameter Store and writes it to `config.json` in the S3 bucket during deployment.

## Building for Production

To build the frontend for production, run:

```bash
npm run build
```

This creates an optimized `build/` folder that can be deployed using the CDK stack. The CDK stack will:
1. Deploy the contents of the `build/` folder to an S3 bucket
2. Create a CloudFront distribution for the S3 bucket
3. Generate and deploy the `config.json` file with values from AWS Parameter Store

## Deployment

The deployment process is fully automated through the CDK stack:

1. Build the frontend: `npm run build`
2. Deploy using CDK: `cdk deploy`

The CDK stack handles:
- Creating and configuring the S3 bucket
- Setting up CloudFront distribution
- Configuring Route53 DNS records
- Deploying the frontend build
- Creating and deploying the `config.json` file with SSM Parameter Store values