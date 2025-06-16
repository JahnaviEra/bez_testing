import boto3, logging, json
from dateutil.relativedelta import relativedelta
from datetime import datetime

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')
workflow_mapping_table = dynamodb.Table('agent_workflow_mapping')
sfunc = boto3.client('stepfunctions')

# Import from bez resources
from bez_utility.bez_metadata_agents import _check_user_agent_access
from bez_utility.bez_metadata_messages import _create_message, _get_msg_by_msgid
from bez_utility.bez_metadata_chats import _check_user_chat_access, _create_chat, _get_chat_by_chatid

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _mda_expert_response(event):
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
        input_date = body.get('reporting_date')
        year, month = map(int, input_date.split('-'))
        first_day = datetime(year, month, 1)
        reporting_date = (first_day + relativedelta(months=1) - relativedelta(days=1)).strftime('%Y-%m-%d')
        if not reporting_date:
            return {"statusCode": 400,
                    "body": json.dumps({"error": "User Input is a required field. Please try again."})}
        agent_id = (agent_int_uid.split('-'))[:3][0]
        message_data = {
            "agent_int_uid": agent_int_uid,
            "chat_id": chat_id,
            "user_input": reporting_date,
            "expiry_in_days": 30,
            "status": "in_progress"
        }
        message_id = _create_message(message_data)
        logger.info(f"Message stored with ID: {message_id}")
        wkflow_mapping = workflow_mapping_table.query(IndexName='agent_id-index',
                                                      KeyConditionExpression="agent_id = :aid",
                                                      ExpressionAttributeValues={
                                                          ":aid": agent_id})["Items"]
        wkflow_mapping_order = sorted(wkflow_mapping, key=lambda x: x['workflow_id'])
        start_response = sfunc.start_execution(
            stateMachineArn='arn:aws:states:us-east-1:664418992073:stateMachine:Bez-MDAExpert',
            input=json.dumps({
                "user_id": user_id,
                "agent_int_uid": agent_int_uid,
                "user_prompt": reporting_date,
                "wkflow_mapping": wkflow_mapping_order,
                "session_id": session_id,
                "message_id": message_id
            })
        )
        execution_arn = start_response['executionArn']
        if not execution_arn:
            return {"statusCode": 400, "body": json.dumps({"message": "Execution Failed"})}
        return {"statusCode": 200,
                "body": json.dumps({"message_id": message_id, "executionArn": start_response['executionArn'], "chat_id": chat_id})}
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error add MFA info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }