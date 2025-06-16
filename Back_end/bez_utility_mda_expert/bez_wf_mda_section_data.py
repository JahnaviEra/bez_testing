import json, logging

# import from bez resources
from bez_utility.bez_utils_aws import _read_s3, _write_s3
from bez_utility.bez_utils_bedrock import _get_ai_response

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
BUCKET_NAME = "bez-dev"

def _wf_mda_section_data(event):
    try:
        logger.info(f"Received event: {event}")
        section = event.get("section")
        report_data = event.get("report_data")
        agent_int_uid = event.get("agent_int_uid")
        integration_id = event.get("integration_id")
        execution_id = event.get("execution_id")
        reporting_date = event.get('user_prompt')
        s3_bucket = event["agent_training_s3_bucket"]
        s3_key = event["agent_training_s3_key"]
        base_training = _read_s3(s3_bucket, s3_key) + f"\nCreate the report with reporting date of {reporting_date}"
        prompt = base_training + f"""\nUse the title of the section as {section.get('section_title')}
                Here is the instruction for the section: {section.get('instruction')}\n
                If data is not present in the reports for this section, simply say that there is no data. Don't suggest how the user should proceed.
                Use the following reports and data"""
        for section_report in section["report_data"]:
            report_name = section_report["report_name"]
            prompt += f"Report Name: {report_name}"
            for report in report_data:
                if report.get("map_index") == section_report["report_id"]:
                    section_report['s3_key'] = report['s3_key']
                    report_s3_data = _read_s3(BUCKET_NAME, section_report['s3_key'])
                    prompt += f"Report data: {report_s3_data}"
        prompt += (f"\n\nProvide your analysis in Markdown format, but start with Heading Level 2 since Heading Level 1 uses text that is too large. "
                   f"In addition to sentences, please use tables and bullets points where it makes sense.  "
                   f"Do not insert 'Management Discussion & Analysis (MD&A)' as a section header.")
        section_text = _get_ai_response({"prompt": prompt})
        section_S3_key = f"{integration_id}/{agent_int_uid}/mda_reports/{execution_id}_{section.get('section_title')}_{section.get('section_order')}"
        _write_s3(BUCKET_NAME, section_S3_key, section_text)
        return {"section_key": section_S3_key, "section_order": section.get('section_order')}
    except Exception as e:
        raise Exception(f"Workflow Error: {str(e)}")