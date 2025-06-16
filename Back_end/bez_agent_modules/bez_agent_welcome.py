import json, logging

# import from bez resources
from bez_utility.bez_metadata_agents import _get_details_for_agentintuid, _check_user_agent_access
from bez_utility.bez_metadata_users import _get_user_by_id
from bez_utility.bez_utils_bedrock import _get_ai_response
from bez_utility.bez_metadata_chats import _create_chat
from bez_utility.bez_utils_aws import _get_record_from_table

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _agent_welcome(event):
    try:
        logger.info(f'Received event: {event}')
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        session_id = event.get("requestContext", {}).get("authorizer", {}).get("session_id", None)
        agent_int_uid = event.get('queryStringParameters', {}).get('agent_int_uid', None)
        logger.info(f"User ID: {user_id}, Agent Int Uid: {agent_int_uid}")
        if not user_id:
            return {"statusCode": 400, "body": json.dumps({"error": "User Id is a required field. Please re-login to try again."})}
        if not agent_int_uid:
            return {"statusCode": 400, "body": json.dumps({"error": "Please select an agent to continue."})}
        # Access check
        user_access = _check_user_agent_access(user_id, agent_int_uid)
        logger.info(f"user_access: {user_access}")
        user = _get_user_by_id({"user_id": user_id})
        first_name = user.get("first_name", "User")
        logger.info(f"User: {user}")
        agent_persona = _get_details_for_agentintuid(agent_int_uid)
        agent_id = agent_int_uid[:3]
        agent_record = _get_record_from_table({
            "table_name": "agent_list",
            "keys": {"agent_id": agent_id},
            "gsi_name": ""
        })
        welcome_prompt_template = agent_record.get("welcome_prompt", "")
        agent_name = agent_persona.get("agent_name", " ")
        agent_type = agent_persona.get("agent_type", " ")
        example_message = agent_record.get("example", "")
        if not welcome_prompt_template and not example_message:
            return {"statusCode": 500, "body": json.dumps({"error": "No welcome prompt or example message configured for this agent."})}

        formatted_prompt = welcome_prompt_template.format(
            first_name=first_name,
            agent_name=agent_name,
            agent_type=agent_type
        )
        full_prompt = (
            f"Agent Instruction:\n{formatted_prompt}\n\n"
            f"Here's an example message the agent might say:\n\"{example_message}\"\n\n"
            f"Now, generate a personalized, friendly welcome message for a user named {first_name}. "
            "It should align with the agent's tone and intent."
        )
        ai_response = _get_ai_response({"prompt": full_prompt})
        # Create chat session
        chat_id = _create_chat({
            "expiry_in_days": 7,
            "agent_int_uid": agent_int_uid,
            "session_id": session_id
        })
        logger.info(f"Chat ID: {chat_id}")
        result = {
            "welcome_message": ai_response,
            "agent_type": agent_type,
            "chat_id": chat_id
        }
        logger.info(f"Result: {result}")
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error add MFA info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }