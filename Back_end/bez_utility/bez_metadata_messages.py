import json, time, logging
import boto3
from botocore.exceptions import ClientError

# import from bez resources
from bez_utility.bez_utils_common import _generate_uid
from bez_utility.bez_utils_aws import _check_record_exists, _update_data_in_table, _get_record_from_table
from bez_utility.bez_metadata_agents import _check_user_agent_access
from bez_utility.bez_metadata_chats import _check_user_chat_access, _populate_chat_theme

# Initialize resources
dynamodb = boto3.resource('dynamodb')

# Calling resources
msgs_table = dynamodb.Table("message_details")

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _get_message_id():
    try:
        message_id = _generate_uid({"n": "16"})
        print('Message id is:', message_id)
        message_id_exists = _check_record_exists({"table_name": "message_details", "keys": {"message_id": message_id}, "gsi_name": ""})
        # print('Chat Exists:', message_id)
        if message_id_exists:
            _get_message_id()
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error
    logger.info(f'Unique Chat id is:{message_id}')
    return message_id

def _is_firstfew_message(chat_id, agent_int_uid):
    if not agent_int_uid or not chat_id:
        raise Exception("Function Error Required parameters missing.")
    try:
        msgs = msgs_table.query(
            IndexName="agent_int_uid-chat_id-index",
            KeyConditionExpression="agent_int_uid = :uid AND chat_id = :chat_id",
            ExpressionAttributeValues={
                ":uid": agent_int_uid,
                ":chat_id": chat_id
            }
        )
        if len(msgs.get('Items', [])) < 3:
            logger.info(f"Proceeding to populate chat theme for agent_int_uid: {agent_int_uid} and chat_id: {chat_id}.")
            return True
        else:
            logger.info(f"Skipping chat theme population for agent_int_uid: {agent_int_uid} and chat_id: {chat_id}.")
            return False
    except Exception as e:
        logger.error(f"Error querying DynamoDB: {str(e)}", exc_info=True)
        raise Exception(f"Function Error {e}") 

def _create_message(data):
    try:
        message_id = _get_message_id() 
        agent_int_uid = data.get("agent_int_uid", "")
        chat_id = data.get("chat_id", "")
        user_input = data.get("user_input", "")
        is_first = _is_firstfew_message(chat_id, agent_int_uid)
        if is_first:
            chat_theme = _populate_chat_theme(chat_id, user_input)
        current_time = int(time.time())
        expiry_in_days = data.get("expiry_in_days", 30)
        logger.info(f'Expiry in days: {expiry_in_days}')
        ttl_time = current_time + (int(expiry_in_days) * 24 * 60 * 60)
        item = {
            "message_id": message_id,
            "agent_int_uid": agent_int_uid,
            "chat_id": chat_id,
            "created_at": str(int(time.time())),
            "ttl": str(ttl_time),
            "summarized": False,
            "user_input": user_input
        }
        logger.info(f'Item inserted to Message table: {item}')
        response = msgs_table.put_item(Item=item)
        logger.info('Message created in Messages table')
        return message_id
    except ClientError as e:
        logger.error(f"Error storing Chat: {e.response['Error']['Message']}")
        return {"error": e.response['Error']['Message']}

def _mark_star_message(event):
    try:
        logger.info(f'Received event: {event}')
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        agent_int_uid = event.get('queryStringParameters').get('agent_int_uid', None)
        if not user_id:
            return {"statusCode": 400, "body": "User Id is a required field. Please re-login to try again."}
        elif not agent_int_uid:
            return {"statusCode": 400, "body": "Please select an agent to continue."}
        user_access = _check_user_agent_access(user_id, agent_int_uid)
        chat_id = event.get('queryStringParameters').get('chat_id')
        chat_access = _check_user_chat_access(user_id, chat_id)
        body = json.loads(event.get("body", "{}"))
        message_id = body.get('message_id')
        status_str = body.get('is_starred')
        if not message_id or not status_str:
            return {'statusCode': 400, 'body': 'Please select a message_id and a specific action before trying again.'}
        if status_str.lower() == 'true':
            is_starred = 'true'
        elif status_str.lower() == 'false':
            is_starred = 'false'
        else:
            return {
                'statusCode': 400,
                'body': 'Invalid message status, must be either true or false'}
        _update_data_in_table({
            "table_name": "message_details",
            "key": "message_id",
            "key_value": str(message_id),
            "update_data": {"is_starred": is_starred}
        })
        result = {"message": f"Star status of message {message_id} is updated."}
        return {'statusCode': 200, 'body': json.dumps(result)}
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})}

def _get_starred_messages(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        agent_int_uid = event.get('queryStringParameters', {}).get('agent_int_uid', None)
        if not user_id:
            return {"statusCode": 400, "body": "User Id is a required field. Please re-login to try again."}
        elif not agent_int_uid:
            return {"statusCode": 400, "body": "Please select an agent to continue."}

        sessions = _get_record_from_table({
            "table_name": "sessions",
            "keys": {"user_id": user_id},
            "gsi_name": "user_id-index"
        })
        session_ids = [s["session_id"] for s in sessions]
        if not session_ids:
            return {"statusCode": 200, "body": json.dumps({"starred_messages": []})}
        chat_ids = []
        for session_id in session_ids:
            chats = _get_record_from_table({
                "table_name": "chat_details",
                "keys": {
                    "session_id": session_id,
                    "agent_int_uid": agent_int_uid
                },
                "gsi_name": "session_id-agent_int_uid-index"
            })
            chat_ids.extend([chat["chat_id"] for chat in chats])
        if not chat_ids:
            return {"statusCode": 200, "body": json.dumps({"starred_messages": []})}
        # Query all starred messages for this agent in one go
        response = msgs_table.query(
            IndexName="agent_int_uid-is_starred-index",
            KeyConditionExpression="agent_int_uid = :uid AND is_starred = :flag",
            ExpressionAttributeValues={
                ":uid": agent_int_uid,
                ":flag": "true"
            }
        )
        all_starred = response.get('Items', [])
        # Filter only user's chats
        starred_messages = [msg for msg in all_starred if msg.get("chat_id") in chat_ids]
        starred_messages.sort(key=lambda x: int(x.get("created_at", 0)), reverse=True)
        return {"statusCode": 200, "body": json.dumps({"starred_messages": starred_messages})}
    except Exception as e:
        logger.error(f"Error retrieving starred messages: {str(e)}", exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": f"Error retrieving starred messages: {str(e)}"})}

def _get_messages(chat_id):
    try:
        response = msgs_table.query(
            IndexName="chat_id-created_at-index",
            KeyConditionExpression="chat_id = :c_id",
            ExpressionAttributeValues={":c_id": chat_id},
            ScanIndexForward=True
        )
        messages = response.get('Items', [])
        logger.info(f'Messages fetched for chat id {chat_id}: {messages}')
        return messages
    except ClientError as e:
        logger.error(f"Error fetching messages: {e.response['Error']['Message']}")
        return {"error": e.response['Error']['Message']}

def _update_msg_status(msg_id, status):
    try:
        _update_data_in_table({
            "table_name": "message_details",
            "key": "message_id",
            "key_value": str(msg_id),
            "update_data": {"status": status}
        })
        logger.info("Successfully updated message status")
        return "Successfully updated message status"
    except Exception as e:
        raise Exception(f"Function Error {str(e)}")

def _get_msg_by_msgid(msg_id):
    try:
        msg = msgs_table.query(
            KeyConditionExpression= "message_id = :m_id",
            ExpressionAttributeValues={
                ":m_id": msg_id})
        logger.info(msg["Items"][0])
        return msg["Items"][0]
    except Exception as e:
        raise Exception(f"Function Error {str(e)}")

def _update_msg_output(msg_id, output):
    try:
        _update_data_in_table({
            "table_name": "message_details",
            "key": "message_id",
            "key_value": str(msg_id),
            "update_data": {"ai_response": output}
        })
        logger.info("Successfully updated response in msg table.")
        return "Successfully updated message output"
    except Exception as e:
        raise Exception(f"Function Error {str(e)}")