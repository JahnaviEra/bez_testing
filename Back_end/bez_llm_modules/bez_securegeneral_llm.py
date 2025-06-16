import json, logging
from datetime import datetime

# Import from bez resources
from bez_utility.bez_metadata_messages import _create_message, _get_msg_by_msgid, _update_msg_output
from bez_utility.bez_metadata_chats import _check_user_chat_access, _create_chat, _get_chat_by_chatid
from bez_utility.bez_utils_aws import _get_record_from_table
from bez_utility.bez_utils_bedrock import _get_ai_response_with_llm
from bez_utility.bez_metadata_agents import _check_user_agent_access,_get_privileges_by_user_for_agent

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
BUCKET_NAME = "bez"

def _secure_chat(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        agent_int_uid = event.get('queryStringParameters').get('agent_int_uid')
        if not user_id:
            return {"statusCode": 400,
                    "body": json.dumps({"error": "User Id is a required field. Please re-login to try again."})}
        if not agent_int_uid:
            return {"statusCode": 400, "body": json.dumps({"error": "Please select an agent to continue."})}
        user_access = _check_user_agent_access(user_id, agent_int_uid)
        session_id = event.get("requestContext", {}).get("authorizer", {}).get("session_id", None)
        is_restore = event.get('queryStringParameters').get('is_restore', False)
        message_id = event.get('queryStringParameters').get('message_id', '')
        chat_id = event.get('queryStringParameters').get('chat_id', '')
        if message_id:
            message = _get_msg_by_msgid(message_id)
            chat_id = message["chat_id"]
        if not chat_id:
            return {"statusCode": 400, "body": "Please select a chat to continue."}
        chat_access = _check_user_chat_access(user_id, chat_id)
        if is_restore:
            hist_chat_id = chat_id
            hist_chat = _get_chat_by_chatid(hist_chat_id)
            hist_session_id = hist_chat["session_id"]
            if (chat_id and hist_session_id != session_id) or message_id:
                new_chat_data = {
                    "agent_int_uid": agent_int_uid,
                    "session_id": session_id,
                    "hist_chat_id": hist_chat_id
                }
                chat_id = _create_chat(new_chat_data)
        logger.info(f'Chat ID: {chat_id}')
        body = json.loads(event.get("body", "{}"))
        user_prompt = body["user_prompt"]
        if not user_prompt:
            return {"statusCode": 400,
                    "body": json.dumps({"error": "User Input is a required field. Please try again."})}
        agent = _get_privileges_by_user_for_agent(user_id,agent_int_uid)
        agent_record = agent[0]
        llm_id = agent_record.get("llm_id")
        llm_model = _get_record_from_table({"table_name": "list_of_llm",
                                        "keys": {"llm_id": llm_id}})
        logger.info(llm_model)
        if not llm_model:
            return {"statusCode": 400, "body": json.dumps({"error": "Model not found"})}
        message_data = {
            "agent_int_uid": agent_int_uid,
            "chat_id": chat_id,
            "user_input": user_prompt,
            "llm_model": llm_model,
            "expiry_in_days": 30,
            "status": "in_progress"
        }
        message_id = _create_message(message_data)
        logger.info(f"Message stored with ID: {message_id}")
        current_date = datetime.now().strftime("%d %B %Y")
        prompt = f"\n\nHuman: {user_prompt}\n\n(Current date is: {current_date}\n\nAssistant:"
        prompt += """\n\n\n\n\n\nFormatting:
                Use Markdown formatting in your response:
                Use `###` for headings.
                Use tables for structured data.
                Use code blocks when presenting code or JSON."""
        request_body_template = llm_model.get("request_body", "")
        try:
            escaped_value = json.dumps(prompt)[1:-1]
            request_body = request_body_template.replace("{{prompt}}", escaped_value)
            request_body = json.loads(request_body)
        except json.JSONDecodeError as e:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Invalid JSON after prompt substitution: {str(e)}"})
            }
        response_text = _get_ai_response_with_llm({"request_body": request_body, "model": llm_model, "temperature": 0.5})
        _update_msg_output(message_id, response_text)
        return {"statusCode": 200, "body": json.dumps({"response": response_text, "message_id": message_id, "chat_id": chat_id})}
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error add MFA info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }