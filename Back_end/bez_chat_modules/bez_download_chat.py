import json, logging, os

# import from bez resources
from bez_utility.bez_metadata_agents import _check_user_agent_access, _get_details_for_agentintuid
from bez_utility.bez_metadata_chats import _check_user_chat_access
from bez_utility.bez_metadata_messages import _get_messages
from bez_utility.bez_metadata_users import _get_user_by_id
from bez_utility.bez_utils_pdf import _convert_to_pdf
from bez_utility.bez_utils_aws import _write_s3, _get_presigned_url

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
BUCKET_NAME = "bez"

def _download_chat(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        env = event.get("headers", {}).get("env", None)
        if not user_id:
            return {"statusCode": 400, "body": "User Id is a required field. Please re-login to try again."}
        agent_int_uid = event['queryStringParameters'].get('agent_int_uid', None)
        _check_user_agent_access(user_id, agent_int_uid)
        chat_id = event.get('queryStringParameters').get('chat_id')
        chat_access = _check_user_chat_access(user_id, chat_id)
        msgs = _get_messages(chat_id)
        agent_details = _get_details_for_agentintuid(agent_int_uid)
        user_details = _get_user_by_id({"user_id":user_id})
        msg_data = []
        user_name = f"{user_details["first_name"]} {user_details["last_name"]}"
        for msg in msgs:
            ai_response = msg.get("ai_response",None)
            if ai_response:
                ai_response = json.loads(msg['ai_response'])
                ai_body = ai_response['body']
                cleaned = ai_body.strip().lstrip('"').rstrip('"')
                normalized = cleaned.replace('\\\\n', '\\n').replace('\\n', '\n')

                # Extract JSON part after 'json\n'
                json_part = normalized.split('json\n', 1)[-1]

                # Remove real newlines (they break JSON parsing)
                json_part = json_part.replace('\n', '')

                # Decode escape sequences
                json_part = bytes(json_part, "utf-8").decode("unicode_escape")

                # Keep only up to the first closing brace
                json_part = json_part[:json_part.find('}')+1]
                try:
                # Now parse the JSON
                    data = json.loads(json_part)
                     # Get the Answer
                    ai_answer = data["Answer"]
                except Exception as e:
                    ai_answer = ai_body
            else:
                ai_answer =   ""
            msg_data.append({
                f"User {user_name}" : msg["user_input"],
                f"Agent {agent_details["agent_name"]}" : ai_answer,
                "created_at": msg.get("created_at","")
            })
        logger.info(msg_data)
        if msg_data:
            pdf_format = _convert_to_pdf(msg_data)
            bucket_name = f"{BUCKET_NAME}-{env}"
            pdf_file_key = f"integration_id/agent_int_uid/chat-history/{chat_id}.pdf"
            _write_s3(bucket_name, pdf_file_key, pdf_format)
            presigned_url = _get_presigned_url(bucket_name, pdf_file_key, 600)
        else:
            return {"statusCode": 400, "body": json.dumps({"error":"No messages available to download."})}
        return {"statusCode": 200,
            "body": json.dumps({"message": "Chat download initiated successfully.", "presigned_url":presigned_url})}
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error fetching agent info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"Error fetching agent info: {str(e)}"})}