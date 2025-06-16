import json, logging, boto3

# import from bez resources
from bez_utility.bez_utils_aws import _read_s3, _write_s3,_get_files_s3
from bez_utility.bez_utils_bedrock import _get_ai_response

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
BUCKET_NAME = "bez-dev"

dynamodb = boto3.resource('dynamodb')
message_table = dynamodb.Table('message_details')


system_instruction_template = """
    You are a Financial Analyst with a deep understanding of Financial KPIs.
    Your task is to answer a user's query using the provided data. Follow these guidelines:
      Respond strictly based on the given data — do not include any external or additional information.
      Return your response in a JSON format with the key "Answer" and value should always be in String format.
      Include the time period(s) referenced in your response explicitly.
      Do not round off any numerical values — preserve full precision.
      Ensure to include a SmartSummary or KeyInsights after tables in your response.
      if you are unable to answer the user's query based on the provided context, then respond stating that I don't have this information from the reports I have. Try enabling the live connection by unchecking the box.
    Formatting:
      Use Markdown formatting in your response:
        Esnure to use `###` tags for Headings and `@@@` tags for Sub Headings.
        Use tables for structured data. Always show months, years, and relevant periods as columns, and KPIs or metrics as rows.
        Use code blocks when presenting code or JSON.
    Here is the content to be used:
    """
def _wf_mda_qna(event):
    try:
        agent_int_uid = event.get("agent_int_uid")
        user_prompt = event.get('user_prompt')
        bucket_name = event.get("agent_training_s3_bucket")
        message_id = event.get('message_id')
        #path = bez-dev/mda_report/001-35897412-46253595/report_data/
        s3_path = f'mda_report/{agent_int_uid}/report_data/'
        objects = _get_files_s3(bucket_name, s3_path)  
        prompt = ""
        for object in objects:
            print(prompt)
            data = _read_s3(bucket_name, object)
            report_name = str(object).split('.')[0]
            prompt += f"""This is the report name: {report_name}
            Here is the data:
            {data}"""
        full_prompt = f"{system_instruction_template} {prompt}, here is the user's question {user_prompt}"
        response_text = _get_ai_response({"prompt": full_prompt})

        if message_id:
            message_table.update_item(
                Key={"message_id": message_id},
                UpdateExpression="SET ai_response = :resp",
                ExpressionAttributeValues={":resp": json.dumps(response_text)}
            )

        return {
            "statusCode": 200,
            "body": json.dumps(response_text)}
    except Exception as e:
        raise Exception(f"Workflow Error: {str(e)}")