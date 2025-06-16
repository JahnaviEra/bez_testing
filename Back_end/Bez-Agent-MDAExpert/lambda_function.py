import json, logging
from importlib import import_module

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Define route mappings for cleaner dispatch
PATH_MAP = {
    "/mda_expert": {"POST": "bez_mda_expert._mda_expert_response"},
    "/get_mda_report_params": {"GET": "bez_mda_report_params._get_mda_source_report_params"},
    "/mda_default_prefs": {"GET":"bez_mda_prefs._get_prefs",
                               "POST":"bez_mda_prefs._update_prefs"}
}

WORKFLOWS_MAP = {
    "_wf_mda_params_report": "bez_wf_mda_params_report._wf_mda_params_report",
    "_wf_mda_section_data":"bez_wf_mda_section_data._wf_mda_section_data",
    "_wf_final_mda_report":"bez_wf_final_mda_report._wf_final_mda_report",
    "_wf_mda_qna":"bez_wf_mda_qna._wf_mda_qna"
}

# Standard CORS headers for all responses
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type"
}

def _add_headers_to_resp(response):
    """Add CORS headers to the response."""
    response['headers'] = CORS_HEADERS
    return response


def _get_path_handler(path, method, workflow, event):
    if path:
        if path not in PATH_MAP or method not in PATH_MAP[path]:
            return None
        handler = PATH_MAP[path][method]
    elif workflow:
        if workflow not in WORKFLOWS_MAP:
            return None
        handler = WORKFLOWS_MAP[workflow]
    # Import and return the handler function
    logger.info(handler)
    module_path, function_name = handler.rsplit('.', 1)
    if path:
        module = import_module(f"bez_mda_modules.{module_path}")
    elif workflow:
        module = import_module(f"bez_utility_mda_expert.{module_path}")
    return getattr(module, function_name)


def lambda_handler(event, context):
    try:
        logger.info(event)
        path = event.get("resource")
        method = event.get("httpMethod")
        workflow = event.get("workflow_function")
        handler_func = _get_path_handler(path, method, workflow, event)
        if handler_func:
            response = handler_func(event)
        else:
            logger.info("Invalid request: No matching route found")
            response = {
                'statusCode': 400,
                'body': json.dumps({'error': 'This is not a valid request. Please check and try again.'})
            }
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        elif "Workflow Error:" in str(e):
            raise Exception({"error": str(e)[len("Workflow Error: "):]})
        else:
            logger.error(f"Error fetching agent info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"message": f"Error fetching agent info: {str(e)}", "error": str(e)}),}
        response = {
            'statusCode': 400,
            'body': json.dumps({
                'error': f'Request processing error: {str(e)}. Please try again.'
            })
        }
    if path:
        return _add_headers_to_resp(response)
    elif workflow:
        return response