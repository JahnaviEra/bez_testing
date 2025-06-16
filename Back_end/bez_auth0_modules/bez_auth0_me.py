import json, logging

# import from bez resources
from bez_utility.bez_metadata_users import _get_user_by_id

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _me(event):
    try:
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        logger.info(user_id)
        user = _get_user_by_id({"user_id":user_id})
        result =  {"data":user}
        if 'otp' in user:
            del user['otp']
        if 'otp_expiration' in user:
            del user['otp_expiration']
        lambda_response = {
                    'statusCode': 200,
                    'body': json.dumps(result)
        }                
        return lambda_response
    except KeyError as e:
        lambda_response = {
            'statusCode': 400,
            'body': json.dumps({'error': f'Missing parameter: {str(e)}'})
        }
        return lambda_response
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error get user(me) info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }