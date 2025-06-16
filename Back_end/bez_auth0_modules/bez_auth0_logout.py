import json, logging, time

# import from bez resources
from bez_utility.bez_utils_aws import _update_data_in_table

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _logout(event):
    try:
        logger.info(f"Received event: {event}")
        session_id = event.get("requestContext", {}).get("authorizer", {}).get("session_id", None)
        expires_at = str(int(time.time()))
        update_user = _update_data_in_table({"table_name": "sessions", "key": "session_id", "key_value": session_id, "update_data": {"expires_at": expires_at}})     
        result =  {"data":"You have been successfully logged out!"}
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
            logger.error(f"Error logout info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }