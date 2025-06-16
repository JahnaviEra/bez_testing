import json, logging

# import from bez resources
from bez_utility.bez_utils_aws import _read_s3, _write_s3
from bez_utility.bez_utils_bedrock import _get_ai_response

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
BUCKET_NAME = "bez-dev"

def _wf_final_mda_report(event):
    try:
        sections = event.get("sections")
        s3_bucket = event.get("agent_training_s3_bucket")
        s3_key = event.get("agent_training_s3_key")
        reporting_date = event.get('user_prompt')
        agent_int_uid = event.get("agent_int_uid")
        integration_id = event.get("integration_id")
        execution_id = event.get("execution_id")
        sorted_sections = sorted(sections, key=lambda x: x['section_order'])
        full_response = ""
        for section in sorted_sections:
            full_response += _read_s3(BUCKET_NAME, section["section_key"])
        # logger.info(full_response)
        prompt = _read_s3(s3_bucket, s3_key)
        prompt += f"The report created by your team is as follows: {full_response}"
        edited_response = {"Answer": _get_ai_response({"prompt": prompt})}
        logger.info(full_response==edited_response)
        message_id= event.get("message_id")
        report_S3_key =f"{integration_id}/{agent_int_uid}/chat_history/{message_id}"
        _write_s3(BUCKET_NAME, report_S3_key, json.dumps(edited_response))
        return report_S3_key
    except Exception as e:
        raise Exception(f"Workflow Error: {str(e)}")