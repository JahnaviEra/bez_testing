import json, logging
from importlib import import_module

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Define route mappings for cleaner dispatch
ROUTE_MAP = {
    "/login": {"POST": "bez_auth0_login._login"},
    "/addmfa": {"POST": "bez_auth0_addmfa._addmfa"},
    "/mfa-verify": {"POST": "bez_auth0_verifymfa._mfa_verify"},
    "/resend-email-verification": {"POST": "bez_auth0_resendemailverification._resend_email_verification"},
    "/email-available": {"POST": "bez_auth0_emailavailable._email_available"},
    "/signup": {"POST": "bez_auth0_signup._signup"},
    "/me": {"GET": "bez_auth0_me._me"},
    "/forgot-password": {"POST": "bez_auth0_forgotpassword._forgot_password"},
    "/logout": {"GET": "bez_auth0_logout._logout"},
    "/get_doc": {"GET": "bez_auth0_legaldocs._get_doc"},
    "/reset-mfa": {
        "POST": {
            "send_reset_email": "bez_auth0_resetmfa._send_reset_email",
            "verify_otp": "bez_auth0_resetmfa._verify_otp"
        }
    }
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

def _get_handler_function(path, method, event):
    """Dynamically resolve the handler function based on route."""
    if path not in ROUTE_MAP or method not in ROUTE_MAP[path]:
        return None
    handler = ROUTE_MAP[path][method]

    # Handle nested routing for reset-mfa
    if isinstance(handler, dict) and path == "/reset-mfa":
        func_param = event.get('queryStringParameters', {}).get('func')
        if func_param not in handler:
            return None
        handler = handler[func_param]
    
    # Import and return the handler function
    module_path, function_name = handler.rsplit('.', 1)
    module = import_module(f"bez_auth0_modules.{module_path}")
    return getattr(module, function_name)

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
            response = {
                'statusCode': 400,
                'body': json.dumps({'error': 'This is not a valid request. Please check and try again.'})
            }            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        response = {
            'statusCode': 400,
            'body': json.dumps({
                'error': f'Request processing error: {str(e)}. Please try again.'
            })
        }        
    return _add_headers_to_resp(response)
