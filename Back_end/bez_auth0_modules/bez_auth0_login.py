import json, logging

# import from bez resources
from bez_utility.bez_validation import PayloadValidator
from bez_utility.bez_utils_aws import _get_secret_value
from bez_utility.bez_utils_auth0 import _get_user_token, _create_jwt_token, _generate_otp

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _login(event):
    try:
        logger.info(f'Received event: {event}')
        body = json.loads(event.get("body", "{}"))
        email = body.get('email')
        password = body.get('password')
        env = event.get("headers", {}).get("env", "dev")
        validation_rules = {
            "email": ["required", "email"],
            "password": ["required"]
        }

        validator = PayloadValidator(body, validation_rules)
        if not validator.is_valid():
            return {
                "statusCode": 400,
                "body": json.dumps({"validation_errors": validator.errors})
            }
        # Fetch config secrets
        config = _get_secret_value({"secret_name": "bezi/dev/env_variables"})
        logger.info(f'Secret value for env variables: {config}')
        response = _get_user_token(email, password, config)
        auth_data = response['data']
        logger.info(f'Auth_data: {auth_data}', )
        if response['status'] == 200:
            access_token = auth_data['access_token']
            id_token = auth_data['id_token']
            try:
                token = _create_jwt_token({"token": id_token, "config": config, "env": env})
                results = {"data": {"mfa_required": False, "token": token}}
                return {
                    'statusCode': 200,
                    'body': json.dumps(results)
                }
            except Exception as e:
                return {
                    'statusCode': 500,
                    'body': str(e)
                }
        elif response['status'] == 403:
            auth_data = response['data']
            # Check for MFA or email verification failure
            if auth_data.get('error') == "mfa_required":
                mfa_token = auth_data.get('mfa_token')
                mfa_result = _generate_otp(config, mfa_token)
                return mfa_result
            elif auth_data.get('error') == 'invalid_grant':
                return {
                    'statusCode': 400,
                    'body': json.dumps({"error": "invalid_grant",
                                        "error_description": "Looks like your credentials are wrong. Please verify and try again."})
                }    #
            else:
                logger.error(f"Authentication failed: {response.status} - {auth_data}")
                return {
                    'statusCode': 400,
                    'body': json.dumps({"error": response.status,
                                        "error_description": auth_data.get('error_description', 'Unknown error')})
                }
        elif response['status'] == 500:
            auth_data = response['data']
            if auth_data.get('error') == 'access_denied' and auth_data[
                'error_description'] == 'Please verify your email before logging in.':
                return {
                    'statusCode': 400,
                    'body': json.dumps(
                        {"error": "access_denied", "error_description": "Please verify your email before logging in."})
                }
            else:
                logger.error(f"Authentication failed: {response.status} - {auth_data}")
                return {
                    'statusCode': 400,
                    'body': json.dumps({"error": response.status,
                                        "error_description": auth_data.get('error_description', 'Unknown error')})
                }
        else:
            logger.error(f"Authentication failed: {response.status} - {auth_data}")
            return {
                'statusCode': 400,
                'body': json.dumps({"error": response.status,
                                    "error_description": auth_data.get('error_description', 'Unknown error')})
            }
    except KeyError as e:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': f'Missing parameter: {str(e)}'})
        }
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error login info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }