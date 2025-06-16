import json, logging

# import from bez resources
from bez_utility.bez_metadata_agents import _check_user_agent_access
from bez_utility.bez_utils_aws import _get_presigned_url
from bez_utility.bez_metadata_chats import _check_user_chat_access
from bez_utility.bez_metadata_messages import _update_msg_status, _get_msg_by_msgid
BUCKET_NAME = "bez"

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _update_agent_status(event):
    try:
        status = (event.get('status')).lower()
        message_id = json.loads(event.get('input')).get('message_id')
        if not status or not message_id:
            raise ValueError("Missing 'status' or 'message_id' in the event.")
        _update_msg_status(message_id, status)
        logger.info(f"Updated status for message_id {message_id} to: {status}")
        return {"statusCode": 200, "body": json.dumps({"message_id": message_id, "status": status})}
    except Exception as e:
        logger.error(f"Error in getting status of Agent: {str(e)}", exc_info=True)
        raise e

def _agent_response_status(event):
    try:
        logger.info(f'Received event: {event}')
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        if not user_id:
            return {"statusCode": 400, "body": "User Id is a required field. Please re-login to try again."}
        agent_int_uid = event['queryStringParameters'].get('agent_int_uid', None)
        if not agent_int_uid:
            return {"statusCode": 400, "body": json.dumps({"error": "Agent selection is required to proceed. Please select an agent to continue."})}
        user_access = _check_user_agent_access(user_id, agent_int_uid)
        message_id = event['queryStringParameters'].get('message_id', None)
        if not message_id:
            return {"statusCode": 400, "body": json.dumps({"error": "Please select a message and try again."})}
        message = _get_msg_by_msgid(message_id)
        msg_status = message['status']
        return {"statusCode": 200, "body": json.dumps({"status": msg_status})}
    except Exception as e:
        logger.error(f"Error in getting status of Agent: {str(e)}", exc_info=True)
        raise e

def _agent_response(event):
    try:
        logger.info(f'Received event: {event}')
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        if not user_id:
            return {"statusCode": 400, "body": "User Id is a required field. Please re-login to try again."}
        agent_int_uid = event['queryStringParameters'].get('agent_int_uid', None)
        if not agent_int_uid:
            return {"statusCode": 400, "body": json.dumps({"error": "Agent selection is required to proceed. Please select an agent to continue."})}
        user_access = _check_user_agent_access(user_id, agent_int_uid)
        chat_id = event['queryStringParameters'].get('chat_id', None)
        chat_access = _check_user_chat_access(user_id, chat_id)
        message_id = event['queryStringParameters'].get('message_id', None)
        if not message_id:
            return {"statusCode": 400, "body": json.dumps({"error": "Please select a message and try again."})}
        message = _get_msg_by_msgid(message_id)
        if message["chat_id"] != chat_id:
            return {"statusCode": 400, "body": json.dumps({"error": "User does not have access to this response."})}
        env = event.get("headers", {}).get("env", None)
        integration_id = (agent_int_uid.split('-'))[:3][1]
        bucket = f"{BUCKET_NAME}-{env}"
        s3_key = f"{integration_id}/{agent_int_uid}/chat_history/{message_id}"
        msg_status = message['status']
        if msg_status == 'SUCCEEDED' or msg_status == 'succeeded':
            presigned_url = _get_presigned_url(bucket, s3_key)
            return {"statusCode": 200, "body": json.dumps({"presigned_url":presigned_url})}
        else:
            return {"statusCode": 400, "body": json.dumps({"error": "The agent workflow completed with errors. Please check your input and try again."})}
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error fetching agent info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"Error fetching agent info: {str(e)}"})}