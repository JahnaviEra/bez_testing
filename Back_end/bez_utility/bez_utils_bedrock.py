import json, boto3, logging, time
from botocore.exceptions import BotoCoreError, ClientError

# Initialize resources
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
inference_profile_arn = "arn:aws:bedrock:us-east-1:664418992073:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0"
titan_profile_arn = "arn:aws:bedrock:us-east-1:664418992073:inference-profile/amazon.titan-image-generator-v1"

def _get_ai_response(data):
    try:
        prompt = data.get("prompt")
        system_prompt = prompt
        if any(word in prompt.lower() for word in ["welcome", "greetings"]):
            temperature = 0.7
        else:
            temperature = 0
        body = json.dumps({
                    "max_tokens": 10000,
                    "messages": [{"role": "user", "content": system_prompt}],
                    "anthropic_version": "bedrock-2023-05-31",
                    "temperature": temperature
                })
        response = bedrock.invoke_model_with_response_stream(body=body, modelId=inference_profile_arn)
        # response_body = json.loads(response['body'].read())
        result = ""
        for event in response['body']:
            chunk = event.get('chunk')
            if chunk:
                chunk_data = json.loads(chunk['bytes'])

                if chunk_data.get('type') == 'content_block_delta':
                    result += chunk_data['delta']['text']
                elif chunk_data.get('type') == 'message_stop':
                    break
        # return response_body.get("content")[0].get("text")
        return result
    except (BotoCoreError, ClientError, Exception) as e:
        raise e

def _generate_avatar_prompt(user_name, max_retries=3, backoff_factor=2):
    prompt = (
        f" Flat vector-style Avatar illustration of a person named {user_name}, front-facing, Corporate bust on a plain white background. "
        "Professional attire (CEO/business suit). Minimalist design,faceless with no facial features - no eyes,eyebrows, nose, lips, or ears. "
        "Show only hair and head shape. cartoon style, clean lines, simple colors. Suitable for user profile icons or infographics."
    )
    model_id = "amazon.titan-image-generator-v2:0"
    body = {"taskType": "TEXT_IMAGE",
        "textToImageParams": {"text": prompt},
        "imageGenerationConfig": {
            "numberOfImages": 1,
            "quality": "standard",
            "cfgScale": 10.0,
            "height": 1024,
            "width": 1024}}
    attempts = 0
    while attempts < max_retries:
        try:
            response = bedrock.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body))
            result = json.loads(response["body"].read())
            image_base64 = result["images"][0]
            return f"data:image/png;base64,{image_base64}"
        except (ClientError, KeyError, json.JSONDecodeError) as e:
            attempts += 1
            wait_time = backoff_factor ** attempts
            if attempts < max_retries:
                logging.warning(f"Error generating avatar: {str(e)}. Retrying in {wait_time} seconds (Attempt {attempts}/{max_retries})")
                time.sleep(wait_time)
            else:
                logging.error(f"Failed to generate avatar after {max_retries} attempts: {str(e)}")
                raise Exception(f"Failed to generate avatar: {str(e)}")

def _get_ai_response_with_llm(data):
    try:
        request_body = data.get("request_body")
        temperature = data.get("temperature", 0.7)
        model = data.get("model")
        response = bedrock.invoke_model(
            body=json.dumps(request_body),
            modelId=model["inference_profile_arn"],
            contentType="application/json",
            accept="application/json"
        )
        response_body = json.loads(response["body"].read())
        rule = json.loads(model.get("parsing_rule", "{}"))
        path = rule.get("path", "")
        for part in path.split("."):
            if "[" in part and "]" in part:
                key, idx = part[:-1].split("[")
                response_body = response_body.get(key, [])
                idx = int(idx)
                if idx < len(response_body):
                    response_body = response_body[idx]
                else:
                    raise Exception("Function Error: Response Parsing issue")
            else:
                if isinstance(response_body, dict):
                    response_body = response_body.get(part)
                else:
                    raise Exception("Function Error: Invalid response ")
        if isinstance(response_body, str):
            response_body = response_body.strip()
        return response_body
    except (BotoCoreError, ClientError, Exception) as e:
        raise e