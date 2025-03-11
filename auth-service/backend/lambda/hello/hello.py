import json

def lambda_handler(event, context):
    # Optionally retrieve authorizer context if available
    auth_context = event.get("requestContext", {}).get("authorizer", {})
    username = auth_context.get("username", "guest")

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps({
            "message": f"Hello {username}, authorization succeeded!"
        })
    }
