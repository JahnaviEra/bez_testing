import json, logging
from importlib import import_module

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
BUCKET_NAME = "bez"

ROUTE_MAP = {
    "/agent_list": {"GET": "bez_agent_list._agent_list"},
    "/agent_details": {"GET": "bez_agent_details._agent_details",
                       "POST": "bez_agent_details._update_agent_details"},
    "/welcome": {"GET": "bez_agent_welcome._agent_welcome"},
    "/star_msg": {"POST": "bez_metadata_messages._mark_star_message"},
    "/get_star_msg": {"GET": "bez_metadata_messages._get_starred_messages"},
    "/chat_history": {"GET": "bez_agent_history._chat_history"},
    "/agent_response": {"GET": "bez_agent_response._agent_response"},
    "/agent_response_status": {"GET": "bez_agent_response._agent_response_status"},
    "/retrieve_chat": {"GET": "bez_agent_history._retrieve_chat"}
}

FUNCTION_MAP = {
    "_update_sfunc_status_in_ddb": "bez_agent_response._update_agent_status",
    "_error_handler": "bez_agent_errorhandler._error_handler"
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


def _get_handler_function(path, method, function, event):
    """Dynamically resolve the handler function based on route."""
    if path:
        if path not in ROUTE_MAP or method not in ROUTE_MAP[path]:
            return None
        handler = ROUTE_MAP[path][method]
    elif function:
        if function not in FUNCTION_MAP:
            return None
        handler = FUNCTION_MAP[function]

    # Import and return the handler function
    module_path, function_name = handler.rsplit('.', 1)
    if path:
        if module_path != 'bez_metadata_messages':
            module = import_module(f"bez_agent_modules.{module_path}")
        else:
            module = import_module(f"bez_utility.{module_path}")
    elif function:
        module = import_module(f"bez_agent_modules.{module_path}")
    return getattr(module, function_name)


def lambda_handler(event, context):
    try:
        logger.info(event)
        path = event.get("resource")
        method = event.get("httpMethod")
        function = event.get("function")
        handler_func = _get_handler_function(path, method, function, event)
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
        if "Error Handler: " in str(e):
            raise Exception(str(e)[len("Error Handler: "):])
        else:
            response = {'statusCode': 400,
                'body': json.dumps({
                    'error': f'Request processing error: {str(e)}. Please try again.'
                })
            }
    if path:
        return _add_headers_to_resp(response)
    elif function:
        return response