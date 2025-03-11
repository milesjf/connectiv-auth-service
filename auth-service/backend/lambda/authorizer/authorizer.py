import os
import logging
import requests
import boto3
import botocore
from authlib.jose import JsonWebToken, JoseError

# -----------------------------------------------------------------------------
# Configuration and Logging
# -----------------------------------------------------------------------------

# Only log errors to minimize exposure of sensitive data.
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

# Validate mandatory environment variables at initialization time.
required_env_vars = ["AWS_REGION", "USER_POOL_ID", "CLIENT_ID", "POLICY_STORE_ID"]
missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
if missing_vars:
    raise EnvironmentError(f"Missing required environment variables: {missing_vars}")

REGION = os.environ["AWS_REGION"]
USER_POOL_ID = os.environ["USER_POOL_ID"]
CLIENT_ID = os.environ["CLIENT_ID"]
POLICY_STORE_ID = os.environ["POLICY_STORE_ID"]

# -----------------------------------------------------------------------------
# JWKS and Clients
# -----------------------------------------------------------------------------
def fetch_jwks(region: str, user_pool_id: str) -> dict:
    """
    Fetch JWKS (public keys) from a Cognito User Pool's JWKS endpoint.
    Returns an empty dict on failure (falls back to a Deny).
    """
    jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
    try:
        response = requests.get(jwks_url, timeout=5)  # Add a timeout for network resilience
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.error("Error fetching JWKS from %s: %s", jwks_url, exc)
        return {}

JWKS_CACHE = fetch_jwks(REGION, USER_POOL_ID)
JWT_VERIFIER = JsonWebToken(["RS256"])
VP_CLIENT = boto3.client("verifiedpermissions", region_name=REGION)

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
def decode_and_validate_token(token: str, jwks: dict) -> dict:
    """
    Decode and validate the JWT token using the provided JWKS.
    Raises JoseError on any validation issue.
    """
    claims = JWT_VERIFIER.decode(token, jwks)
    claims.validate()
    return claims

def refresh_jwks_and_retry(token: str, exc_msg: str) -> dict:
    """
    If we suspect a key is missing or outdated, re-fetch JWKS once and try again.
    Raise the error if it still fails.
    """
    if "Key not found" in exc_msg:
        logger.error("Key not found in JWKS; attempting refresh.")
        new_jwks = fetch_jwks(REGION, USER_POOL_ID)
        # Optionally update global JWKS_CACHE; depends on your caching strategy:
        global JWKS_CACHE
        JWKS_CACHE = new_jwks
        claims = JWT_VERIFIER.decode(token, new_jwks)
        claims.validate()
        return claims
    # If it's a different error, just re-raise.
    raise JoseError(exc_msg)

def validate_claims(claims: dict, client_id: str, region: str, user_pool_id: str) -> None:
    """
    Verify the token claims for audience and issuer matching expectations.
    Raises an Exception if validation fails.
    """
    if claims.get("aud") != client_id:
        raise ValueError("Invalid audience")

    expected_issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
    if claims.get("iss") != expected_issuer:
        raise ValueError("Invalid issuer")

def build_auth_request(
        policy_store_id: str,
        principal_id: str,
        group_value: str,
        custom_attributes: dict,
        action_id: str = "access",
        resource_id: str = "my-resource"
) -> dict:
    """
    Builds the Verified Permissions authorization request for a shape-based Cedar schema.
    This version attaches the principal's custom attributes as ephemeral entity attributes,
    following Cedar's JSON schema format.
    """
    # Helper: Wrap a value as a typed object. Here we assume it's a string.
    def wrap_value(val):
        return {"string": val}

    # Build principal attributes with typed values.
    principal_attributes = {
        "group": wrap_value(group_value)
    }
    for k, v in custom_attributes.items():
        principal_attributes[k] = wrap_value(v)

    return {
        "policyStoreId": policy_store_id,
        "principal": {
            "entityType": "ExampleCo::Connectiv::User",
            "entityId": principal_id
        },
        "action": {
            "actionType": "ExampleCo::Connectiv::Action",
            "actionId": action_id
        },
        "resource": {
            "entityType": "ExampleCo::Connectiv::Resource",
            "entityId": resource_id
        },
        "entities": {
            "entityList": [
                {
                    "identifier": {
                        "entityType": "ExampleCo::Connectiv::User",
                        "entityId": principal_id
                    },
                    "attributes": principal_attributes
                }
            ]
        }
    }

def evaluate_policy(auth_request: dict) -> str:
    """
    Calls Verified Permissions to evaluate the policy and returns 'Allow' or 'Deny'.
    Logs specific AWS client errors if they occur.
    """
    try:
        vp_response = VP_CLIENT.is_authorized(**auth_request)
        decision = vp_response.get("decision", "DENY")
        return "Allow" if decision == "ALLOW" else "Deny"

    except botocore.exceptions.ClientError as exc:
        # Distinguish known AWS errors (e.g. resource not found, invalid request, etc.)
        error_code = exc.response["Error"].get("Code", "Unknown")
        logger.error("Verified Permissions client error [%s]: %s", error_code, exc)
        return "Deny"

    except Exception as exc:
        # Catch-all for other errors
        logger.error("Verified Permissions evaluation error: %s", exc)
        return "Deny"

def generate_policy(principal_id: str, effect: str, resource: str, context_data: dict = None) -> dict:
    """
    Creates an IAM policy document for API Gateway.
    Optional context_data can add custom context fields if needed.
    """
    if context_data is None:
        context_data = {}

    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "execute-api:Invoke",
                "Effect": effect,
                "Resource": resource
            }
        ]
    }
    # Include the "username" in context by default, plus any additional info
    context_data["username"] = principal_id

    return {
        "principalId": principal_id,
        "policyDocument": policy_document,
        "context": context_data
    }

def extract_custom_attributes(claims: dict) -> dict:
    """
    Extract all custom attributes from token claims.
    The attributes in Cognito appear with a "custom:" prefix.
    """
    return {
        key.replace("custom:", ""): value
        for key, value in claims.items()
        if key.startswith("custom:")
    }

# -----------------------------------------------------------------------------
# Lambda Handler
# -----------------------------------------------------------------------------
def lambda_handler(event: dict, context) -> dict:
    """
    Entry point for AWS Lambda to validate a JWT from Cognito and authorize via
    Verified Permissions. Returns an IAM policy (Allow/Deny) for API Gateway.
    """
    principal_id = "unknown"
    effect = "Deny"  # Default to Deny on any failure.

    # Retrieve and strip the Bearer token.
    token = event.get("authorizationToken", "")
    if token.startswith("Bearer "):
        token = token[len("Bearer "):]

    # Attempt to decode and validate the token
    try:
        try:
            claims = decode_and_validate_token(token, JWKS_CACHE)
        except JoseError as token_exc:
            # If the error suggests a missing/outdated key, try refreshing JWKS once
            claims = refresh_jwks_and_retry(token, str(token_exc))

        # Claims are valid; check audience/issuer
        validate_claims(claims, CLIENT_ID, REGION, USER_POOL_ID)

        # Extract principal and group from the claims.
        principal_id = claims.get("cognito:username", "unknown")
        group_value = next(iter(claims.get("cognito:groups", [])), "Unknown")

        # Extract all custom attributes from the token.
        custom_attrs = extract_custom_attributes(claims)

        # Build and evaluate the Verified Permissions authorization request.
        auth_request = build_auth_request(
            POLICY_STORE_ID,
            principal_id,
            group_value,
            custom_attrs,
            action_id="access",         # This matches your "actions" block in the schema
            resource_id="my-resource"   # Or any resource ID you want
        )
        print("Auth request:", auth_request)
        effect = evaluate_policy(auth_request)

    except (JoseError, ValueError) as exc:
        # Log generic error without exposing sensitive data.
        logger.error("Token/Authorization error: %s", exc)
        # effect remains "Deny"

    # Return the IAM policy to API Gateway.
    return generate_policy(principal_id, effect, event.get("methodArn", "*"))
