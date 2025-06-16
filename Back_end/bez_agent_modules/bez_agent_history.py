import json, logging
from datetime import datetime, timedelta, timezone

# import from bez resources
from bez_utility.bez_metadata_agents import _check_user_agent_access
from bez_utility.bez_metadata_chats import _get_chats_by_userid_by_agent, _check_user_chat_access, _get_chat_by_chatid
from bez_utility.bez_metadata_messages import _get_messages, _get_msg_by_msgid

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _chat_history(event):
    try:
        logger.info(f'Received event: {event}')
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        agent_int_uid = event.get('queryStringParameters').get('agent_int_uid', None)
        if not user_id:
            return {"statusCode": 400, "body": "User Id is a required field. Please re-login to try again."}
        if not agent_int_uid:
            return {"statusCode": 400, "body": "Please select an agent to continue."}
        user_access = _check_user_agent_access(user_id, agent_int_uid)
        chats = _get_chats_by_userid_by_agent(user_id, agent_int_uid)
        chats = sorted(chats, key=lambda x: int(x["created_at"]), reverse=True)
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        last_week_start = today_start - timedelta(days=7)
        last_30_days_start = now - timedelta(days=30)
        categorized_chats = {
            "today": [],
            "yesterday": [],
            "previous_7_days": [],
            "previous_30_days": []
            }
        chat_history = []
        for chat in chats:
            logger.info(chat)
            created_at = datetime.fromtimestamp(int(chat["created_at"]), tz=timezone.utc)
            if chat.get("chat_theme", ""):
                chat_data = {
                    "created_at": chat["created_at"],
                    "chat_theme": chat.get("chat_theme",""),
                    "chat_id": chat["chat_id"]
                }
                chat_history.append(chat_data)
                if created_at >= today_start:
                    categorized_chats["today"].append(chat_data)
                elif created_at >= yesterday_start:
                    categorized_chats["yesterday"].append(chat_data)
                elif created_at >= last_week_start:
                    categorized_chats["previous_7_days"].append(chat_data)
                elif created_at >= last_30_days_start:
                    categorized_chats["previous_30_days"].append(chat_data)
        return {
            'statusCode': 200,
            'body': json.dumps({'chat_history': categorized_chats})}
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error fetching agent info: {str(e)}", exc_info=True)
            return {"statusCode": 500, "body": json.dumps({"error": f"Error fetching agent info: {str(e)}"})}

def _retrieve_chat(event):
    try:
        logger.info(f'Received event: {event}')
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        agent_int_uid = event.get('queryStringParameters').get('agent_int_uid', None)
        if not user_id:
            return {"statusCode": 400, "body": "User Id is a required field. Please re-login to try again."}
        if not agent_int_uid:
            return {"statusCode": 400, "body": "Please select an agent to continue."}
        user_access = _check_user_agent_access(user_id, agent_int_uid)
        chat_id = event['queryStringParameters'].get('chat_id', None)
        from_star = event['queryStringParameters'].get('from_star', False)
        message_id = event['queryStringParameters'].get('message_id', None)
        if message_id:
            message = _get_msg_by_msgid(message_id)
            chat_id = message["chat_id"]
        if not chat_id:
            return {"statusCode": 400, "body": "Please select a chat to continue."}
        chat_access = _check_user_chat_access(user_id, chat_id)
        has_historical_chat = True
        current_chat_id = chat_id
        all_messages = []
        next_chat_start = 9999999999999
        while has_historical_chat:
            messages = _get_messages(current_chat_id)
            logger.info(messages)
            if messages:
                for msg in messages:
                    if int(msg["created_at"]) <= int(next_chat_start):
                        all_messages.append(msg)
            chat = _get_chat_by_chatid(current_chat_id)
            if chat.get("hist_chat_id"):
                current_chat_id = chat.get("hist_chat_id")
                next_chat_start = chat.get("created_at")
                has_historical_chat = True
            else:
                has_historical_chat = False
        if from_star:
            star_time = message["created_at"]
            all_messages = [msg for msg in all_messages if msg["created_at"] <=  star_time]
        all_messages.sort(key=lambda msg: int(msg["created_at"]))
        logger.info(f"All messages: {all_messages}")
        return {"statusCode": 200, "body": json.dumps({"data": all_messages})}
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error fetching agent info: {str(e)}", exc_info=True)
            return {"statusCode": 500, "body": json.dumps({"error": f"Error fetching agent info: {str(e)}"})}