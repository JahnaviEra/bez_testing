import json
import logging, time
from bez_utility.bez_utils_bedrock import _get_ai_response
from bez_utility.bez_utils_aws import _get_files_s3, _read_s3
from bez_utility.bez_metadata_agents import _get_details_for_agentintuid

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

system_instruction_template = """
    You are a Financial Analyst with a deep understanding of Financial KPIs.
    Your task is to answer a user's query using the provided data. Follow these guidelines:
      Respond strictly based on the given data — do not include any external or additional information.
      Return your response in a JSON format with the key "Answer" and value should always be in String format.
      Include the time period(s) referenced in your response explicitly.
      Do not round off any numerical values — preserve full precision.
      Ensure to include a SmartSummary or KeyInsights after tables in your response.
      Respond with a boolean key "Valid" — set it to True if the question can be answered (even partially) using the data, otherwise set it to False.
    Formatting:
      Use Markdown formatting in your response:
        Esnure to use `###` tags for Headings and `@@@` tags for Sub Headings.
        Use tables for structured data. Always show months, years, and relevant periods as columns, and KPIs or metrics as rows.
        Use code blocks when presenting code or JSON.
    Here is the content to be used:
      {content}"""

def _wf_qbo_expert_summarize(event):
    try:
        st1 = time.time()
        logger.info(f"Received event: {event}")
        agent_int_uid = event.get("agent_int_uid")
        integration_id = (agent_int_uid.split('-'))[:3][1]
        execution_id = event.get("execution_id")
        bucket_name = event.get('s3_bucket')
        s3_path = f'{integration_id}/{execution_id}'
        objects = _get_files_s3(bucket_name, s3_path)
        user_prompt = event.get("user_prompt")
        dt2 = time.time() - st1
        logger.info(f"Time to read params: {dt2}")
        all_data = []
        for object in objects:
            data = _read_s3(bucket_name, object)
            all_data.append(data)
        dt3 = time.time() - st1 - dt2
        logger.info(f"Time to read s3: {dt3}")
        if not user_prompt:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "User prompt is a required field."})
            }
        system_instruction = system_instruction_template.format(content=all_data)
        full_prompt = f"{user_prompt} {system_instruction}"
        dt4 = time.time() - st1 - dt2 - dt3
        logger.info(f"Time to read prompt: {dt4}")
        response_text = _get_ai_response({"prompt": full_prompt})
        return {
            "statusCode": 200,
            "body": json.dumps(response_text)}
    except Exception as e:
        logger.exception("Unexpected error occurred while generating the response.")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})}

def _wf_generic_response(event):
    try:
        logger.info(f"Received event: {event}")
        user_prompt = event.get("user_prompt")
        valid = event.get("valid")
        agent_int_uid = event.get("agent_int_uid")
        record = _get_details_for_agentintuid(agent_int_uid)
        agent_name = record.get("agent_name")
        system_instruction = f"""
        You are a financial analyst that can answer company specific financial questions, when the data is provided to you. Your name is {agent_name}
            •   Only respond to greetings (e.g., "Hi", "Hello","How are you?" "Good morning") with a polite greeting when user greets you..
            •   For all other messages — including personal questions, requests, or general queries — instead tell the user to ask questions only related to clients/company's financial statements.
            •   Do not answer or explain anything beyond greetings.
            •   Do not provide any suggestions, recommendations, or information from external sources or general knowledge.
            •   Do not use any external knowledge under any circumstances."""
        full_prompt = f'System Instruction: {system_instruction}, User Question:  {user_prompt}'
        response_text = _get_ai_response({"prompt": full_prompt})
        return {
            "statusCode": 200,
            "body": json.dumps(response_text)}
    except Exception as e:
        logger.exception("Unexpected error occurred while generating the response.")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})}