import json, boto3, logging
import http.client
from botocore.exceptions import BotoCoreError, ClientError
from urllib.parse import urlencode
from bez_utility.bez_validation import PayloadValidator

# import from bez resources
from bez_utility.bez_utils_aws import _get_secret_value
from bez_utility.bez_metadata_users import _create_user
from bez_utility.bez_utils_auth0 import _auth0_signup

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _signup(event):
    try:
        logger.info('Received event: {event}')
        body = json.loads(event.get("body", "{}"))
        email = body.get('email')
        password = body.get('password')
        first_name = body.get('first_name')
        last_name = body.get('last_name')
        validation_rules = {
            "email": ["required", "email"],
            "password": ["required", "password"],
            "first_name": ["required", "not_blank", "alpha"],
            "last_name": ["required", "not_blank", "alpha"]
        }
        validator = PayloadValidator(body, validation_rules)
        if not validator.is_valid():
            return {
                "statusCode": 400,
                "body": json.dumps({"validation_errors": validator.errors})
            }
        # Fetch config secrets
        config = _get_secret_value({"secret_name": "bezi/dev/env_variables"})
        logger.info('Secret value for env variables: {config}')
        # Register user in Auth0
        result = _auth0_signup(email, password, first_name, last_name, config)
        logger.info(json.dumps(result))
        if result.get("error") == "User already exists":
            return {
                'statusCode': 400,
                'body': json.dumps({"error": "User already exists in Auth0 database."})
            }
        auth0_id = result.get('_id')
        # Invoke Bezi-Metadata-Users Lambda to create user in DynamoDB
        create_user = _create_user({"auth0_id": auth0_id, "email": email, "first_name": first_name, "last_name": last_name})
        return {'statusCode': 200,
                'body': json.dumps(result)}
    except KeyError as e:
        return {'statusCode': 400,
                'body': json.dumps({'error': f'Missing parameter: {str(e)}'})}
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error signup info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }