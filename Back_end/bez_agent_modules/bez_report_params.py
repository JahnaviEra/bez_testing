import logging, json

from bez_utility.bez_utils_aws import _get_record_from_table

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _get_mda_source_report_params(event):
    try:
        source_name = None
        if event['queryStringParameters']:
            source_name = event['queryStringParameters'].get("source_name")
        if not source_name:
            return {"error": "Missing source_name in headers"}

        data = {
            "table_name": "report_source",
            "keys": {"source_name": source_name}
        }
        record = _get_record_from_table(data)
        if not record or "source_report_params" not in record:
            return {"error": "No data found for the given source_name"}

        return {"source_report_params": record["source_report_params"]}
    except Exception as e:
        if "Function Error:" in str(e):
            error_message = str(e)[str(e).find("Function Error:") + len("Function Error: "):]
            logger.warning(f"Client error when fetching agent profile: {error_message}")
            return {"statusCode": 400, "body": json.dumps({"error": error_message})}
        else:
            logger.error(f"Error creating integrations info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }