import json, logging
from importlib import import_module

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

module_name = "bez_agent_modules"
ROUTE_MAP = {
    "/setup_welcome": {"POST": "bez_setup_welcome._setup_welcome"},
    "/client_list": {"GET": "bez_client_list._client_list"},
    "/int_list_by_client": {"GET": "bez_int_list._int_list_by_client"},
    "/create_client": {"POST": "bez_create_client._create_client"},
    "/create_int": {"POST": "bez_create_int._create_int"},
    "/base_agent": {"GET": "bez_create_agent_profile._get_base_agent_profile"},
    "/save_agent_profile": {"POST": "bez_save_agent_profile._save_agent_profile"},
    "/create_agent_profile": {"POST": "bez_create_agent_profile._create_agent_profile"},
    "/check_int_count": {"GET": "bez_int_list._int_count_by_user"},
    "/agent_persona": {"GET":"bez_agent_persona._get_persona",
                        "POST":"bez_agent_persona._update_persona"},
    "/reset_persona": {"GET":"bez_agent_persona._reset_persona"}
}
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type"
}

def _get_handler_function(path, method, event):
    if path not in ROUTE_MAP or method not in ROUTE_MAP[path]:
        return None
    handler = ROUTE_MAP[path][method]
    module_path, function_name = handler.rsplit('.', 1)
    module = import_module(f"{module_name}.{module_path}")
    return getattr(module, function_name)

def _add_headers_to_resp(response):
    response['headers'] = CORS_HEADERS
    return response

def lambda_handler(event, context):
    try:
        logger.info(event)
        path = event.get("resource")
        method = event.get("httpMethod")
        handler_func = _get_handler_function(path, method, event)
        if handler_func:
            response = handler_func(event)
        else:
            logger.info("Invalid request: No matching route found")
            response = {'statusCode': 400, 'body': json.dumps({'error': 'This is not a valid request. Please check and try again.'})}
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        response = {
            'statusCode': 400, 'body': json.dumps({'error': f'Request processing error: {str(e)}. Please try again.'})}
    return _add_headers_to_resp(response)