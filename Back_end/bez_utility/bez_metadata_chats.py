import json, time, logging
import boto3
from botocore.exceptions import ClientError

#import from bez functions
from bez_utility.bez_utils_common import _generate_uid
from bez_utility.bez_utils_aws import _check_record_exists, _update_data_in_table
from bez_utility.bez_utils_bedrock import _get_ai_response

# Initialize resources
dynamodb = boto3.resource('dynamodb')

# Calling resources
chats_table = dynamodb.Table("chat_details")
sessions_table = dynamodb.Table("sessions")

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _get_chat_id():
    try:
        chat_id = _generate_uid({"n": "8"})
        print('Chat id is:', chat_id)
        chat_id_exists = _check_record_exists({"table_name": "chat_details", "keys": {"chat_id": chat_id}, "gsi_name": ""})
        # print('Chat Exists:', chat_id)
        if chat_id_exists:
            _get_chat_id()
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error
    logger.info(f'Unique Chat id is:{chat_id}')
    return chat_id

def _create_chat(data):
    try:
        chat_id = _get_chat_id() 
        current_time = int(time.time())
        expiry_in_days = data.get("expiry_in_days", 30)
        logger.info(f'Expiry in days: {expiry_in_days}')
        ttl_time = current_time + (int(expiry_in_days) * 24 * 60 * 60) 
        item = {
            "chat_id": chat_id,
            "agent_int_uid": data.get("agent_int_uid", ""),
            "created_at": str(int(time.time())),
            "ttl": str(ttl_time),
            "summarized": False,
            "session_id": data.get("session_id", ""),
            "hist_chat_id":data.get("hist_chat_id","")
        }
        logger.info(f'Item inserted to Chat table: {item}')
        response = chats_table.put_item(Item=item)
        logger.info('Chat created in Chats table')
        return chat_id
    except ClientError as e:
        logger.error(f"Error storing Chat: {e.response['Error']['Message']}")
        return {"error": e.response['Error']['Message']}

def _get_chat_by_chatid(chat_id):
    try:
        chat = chats_table.query(
            KeyConditionExpression= "chat_id = :c_id",
            ExpressionAttributeValues={
                ":c_id": chat_id})
        logger.info(chat["Items"][0])
        return chat["Items"][0]
    except Exception as e:
        return e

def _check_user_chat_access(user_id, chat_id):
    try:
        chat = _get_chat_by_chatid(chat_id)
        logger.info(chat)
        session_id = chat["session_id"]
        session = sessions_table.query(KeyConditionExpression= "session_id = :s_id",
            ExpressionAttributeValues={
                ":s_id": session_id})["Items"][0]
        logger.info(f"Session: {session}")
        if session["user_id"] != user_id:
            raise Exception("Function Error: User does not have access to the chat.")
        return chat
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error

def _get_chats_by_userid_by_agent(user_id, agent_int_uid):
    try:
        chats = chats_table.query(
            IndexName="agent_int_uid-index",
            KeyConditionExpression="agent_int_uid = :a_id",
            ExpressionAttributeValues={":a_id": agent_int_uid}
        )["Items"]
        valid_chats = []
        for chat in chats:
            session_id = chat["session_id"]
            session_result = sessions_table.query(
                KeyConditionExpression="session_id = :s_id",
                ExpressionAttributeValues={":s_id": session_id}
            )
            if session_result["Items"]:
                session = session_result["Items"][0]
                if session["user_id"] == user_id:
                    valid_chats.append(chat)
        logger.info(f"Chats: {valid_chats}")
        return valid_chats
    except Exception as e:
        logger.error(f"Function Error: {e}")
        raise Exception(f"Function Error: {e}")

def _populate_chat_theme(chat_id, user_input):
    try:
        chat = _get_chat_by_chatid(chat_id)
        historical_theme = chat.get("chat_theme", "").strip()
        if not historical_theme:
            system_prompt = (
                "Summarize the following message with a theme in 3-5 words. "
                f"The message is: '{user_input}'. "
                "Return a concise and relevant theme."
            )
        else:
            system_prompt = (
                "Summarize the following conversation with a theme in 3-5 words. Keep it concise. "
                f"The historical theme of the conversation is: '{historical_theme}'. "
                f"The follow-up question is: '{user_input}'. "
                "If the theme between the historical theme and follow-up question differs, prioritize the historical theme. "
                "If the follow-up question aligns with the historical theme, refine the theme to better reflect the new input."
            )
        chat_theme = _get_ai_response({"prompt":system_prompt})
        updated_response = _update_data_in_table({"table_name": "chat_details", "key": "chat_id", "key_value": chat_id, "update_data": {"chat_theme": chat_theme}})
        return chat_theme
    except Exception as e:
        raise Exception(f"Function Error: {e}")