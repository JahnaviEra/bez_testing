import json, logging

from bez_chat_modules.bez_download_chat import _download_chat

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _add_headers_to_resp(data):
    data['headers'] = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }
    return data

def lambda_handler(event, context):
    try:
        logger.info(event)
        path = event.get("resource")
        method = event.get("httpMethod")
        if path == "/download_chat" and method == "GET":
            response = _download_chat(event)
        else:
            response = {'statusCode': 400, 'body': json.dumps({'error': 'This is not a valid request. Please check and try again.'})}
    except Exception as e:
        logger.info(e)
        response = {"error": str(e)}
    if path:
        return _add_headers_to_resp(response)
