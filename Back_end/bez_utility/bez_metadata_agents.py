import logging, boto3, re, time, os, base64
from boto3.dynamodb.conditions import Key

# import from bez resources
from bez_utility.bez_utils_common import _generate_uid
from bez_utility.bez_utils_aws import _check_record_exists, _query_dynamodb, _scan_table_with_filter, _get_presigned_url
from bez_utility.bez_utils_bedrock import _get_ai_response, _generate_avatar_prompt

# Initialize resources
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

#environment variables
BUCKET_NAME = os.environ.get("BUCKET_NAME", "bez")
MAX_IMAGE_SIZE_MB = 2
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024  # 2MB

# Calling resources
agent_table = dynamodb.Table("agent_list")
agent_by_int_table = dynamodb.Table("agent_list_by_int")
agent_privileges_table = dynamodb.Table("agent_privileges")
agent_mda_sections_table = dynamodb.Table("agent_mda_section_report_map")

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _get_agent_details(agent_id):
    try:
        agent_response = agent_table.get_item(Key={"agent_id": agent_id})
        agent_data = agent_response.get("Item")
        if not agent_data:
            raise Exception("Function Error: Agent not found")
        return agent_data
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error

def _get_agent_int_uid(agent_id, int_id):
    try:
        uid = _generate_uid({"n": "8"})
        logger.info(f'Unique id is: {uid}')
        agent_int_uid = f"{agent_id}-{int_id}-{uid}"
        agent_int_uid_exists = _check_record_exists({"table_name": "agent_list_by_int", "keys": {"agent_int_uid": agent_int_uid}, "gsi_name": ""})
        if agent_int_uid_exists:
            _get_agent_int_uid(agent_id, int_id)
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error
    logger.info(f'Unique Agent id is:{agent_int_uid}')
    return agent_int_uid

def _create_agent_by_int_table_record(int_id, agent_int_uid, agent_age, agent_gender, agent_name, agent_type, example_welcome_prompt, skillset, welcome_prompt, profile_pic=None):
    try:
        item = {
            "agent_int_uid": agent_int_uid,
            "agent_age": agent_age,
            "agent_gender": agent_gender,
            "agent_name": agent_name,
            "agent_type": agent_type,
            "example_welcome_prompt": example_welcome_prompt,
            "int_id":  int_id,
            "skillset": skillset,
            "welcome_prompt": welcome_prompt,
            "profile_pic": profile_pic
        }
        agent_by_int_table.put_item(Item=item)
        logger.info(f"Agent list by Int table record created: {item}")
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error

def _create_record_agent_by_int(int_id, agent_int_uid, agent_name, agent_type, skillset, welcome_prompt, profile_pic=None):
    try:
        item = {
            "agent_int_uid": agent_int_uid,
            "agent_name": agent_name,
            "agent_type": agent_type,
            "int_id":  int_id,
            "skillset": skillset,
            "welcome_prompt": welcome_prompt,
            "profile_pic": profile_pic
        }
        agent_by_int_table.put_item(Item=item)
        logger.info(f"Agent list by Int table record created: {item}")
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error

def _get_agent_privilege_id():
    try:
        agent_privilege_id = _generate_uid({"n": "8"})
        logger.info(f'Unique id is: {agent_privilege_id}')
        agent_privilege_id_exists = _check_record_exists({"table_name": "agent_privileges", "keys": {"agent_privilege_id": agent_privilege_id}, "gsi_name": ""})
        if agent_privilege_id_exists:
            _get_agent_privilege_id()
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error
    logger.info(f'Unique Agent Privilege id is:{agent_privilege_id}')
    return agent_privilege_id

def _create_agent_privilege_record(agent_privilege_id, agent_int_uid,agent_persona,  user_id, llm_id=None):
    try:
        item = {
            "agent_privilege_id": agent_privilege_id,
            "agent_int_uid": agent_int_uid,
            "agent_persona":agent_persona,
            "is_active": True,
            "is_deleted": False,
            "is_owner": True,
        "user_id": user_id,
            "llm_id":llm_id
        }
        agent_privileges_table.put_item(Item=item)
        logger.info(f"Agent Privileges record created: {item}")
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error

def _get_agent_privileges_by_user(user_id):
    """Fetch agent privileges for a given user_id."""
    try:
        response = agent_privileges_table.query(
            IndexName="user_id-index",
            KeyConditionExpression=boto3.dynamodb.conditions.Key("user_id").eq(str(user_id))
        )
        return response.get("Items", [])
    except Exception as e:
        logger.info(f"Error fetching agent privileges: {e}")
        raise e

def _get_privileges_by_user_for_agent(user_id, agent_int_uid):
    """Fetch agent privileges for a given user_id."""
    try:
        response = _query_dynamodb({"table_name": "agent_privileges",
                            "gsi_name": "agent_int_uid-user_id-index",
                            "query_params": {
                                "user_id": user_id,
                                "agent_int_uid": agent_int_uid
                            }})
        return response
    except Exception as e:
        logger.info(f"Error fetching agent privileges: {e}")
        raise e

def _get_details_for_agentintuid(agent_int_uid):
    """Fetch agent details from agent_list_by_int."""
    try:
        response = agent_by_int_table.get_item(Key={"agent_int_uid": str(agent_int_uid)})
        agent_data = response.get("Item")
        if not agent_data:
            raise Exception("Function Error: Agent not found")
        return agent_data
    except Exception as e:
        logger.info(f"Error fetching agent {agent_int_uid} details: {e}")
        raise e

def _get_agent_details_by_status(status):
    try:
        logger.info(f"Fetching agent details for status: {status}")
        response = agent_table.query(
            IndexName="agent_status-index",
            KeyConditionExpression=Key("agent_status").eq(status)
        )
        logger.info(f"Agent details fetched successfully: {response}")
        agents_list = response.get("Items", [])
        return agents_list
    except Exception as e:
        logger.info(f"Error fetching agent details: {e}")
        raise e

def _get_clean_folder_name(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())

def _save_agent_pic(image_data, agent_name, agent_int_uid, env, agent_type):
    try:
        error = ""
        profile_pic = ""
        if image_data:
            match = re.match(r'^data:(image/(png|jpeg|jpg));base64,(.+)$', image_data)
            if not match:
                error = "Invalid image format."
            if not error:
                content_type = match.group(1)  # e.g., image/png
                content_type = match.group(1)
                base64_data = match.group(3)
                image_bytes = base64.b64decode(base64_data)
                if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
                    error = "Image is too large. Max size is {MAX_IMAGE_SIZE_MB} MB."
            if not error:
            # Generate a unique filename
                file_extension = content_type.split('/')[-1]
                file_name = f"{_get_clean_folder_name(agent_name)}_{str(time.time())}.{file_extension}"
                agent_type_prefix = f"{_get_clean_folder_name(agent_type)}/"
                agent_int_prefix = f"{agent_type_prefix}{agent_int_uid}/"
                bucket_name = f"{BUCKET_NAME}-{env}"
                file_path =f"{agent_int_prefix}{file_name}"
                try:
                    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=agent_type_prefix, MaxKeys=1)
                    if 'Contents' not in response:
                        s3.put_object(Bucket=bucket_name, Key=agent_type_prefix)
                        logger.info(f"Created folder: {agent_type_prefix}")
                    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=agent_int_prefix, MaxKeys=1)
                    if 'Contents' not in response:
                        s3.put_object(Bucket=bucket_name, Key=agent_int_prefix)
                        logger.info(f"Created folder here: {agent_int_prefix}")
                    s3.put_object(
                        Bucket=bucket_name,
                        Key=file_path,
                        Body=image_bytes,
                        ContentType=content_type  # or 'image/png' etc.
                    )
                    profile_pic = file_path
                    return profile_pic
                except Exception as e:
                    logger.error(f"Unexpected error while upload profile pic on s3: {e}")
                    error = {str(e)}
        if error:
            error = f"Profile image not saved due to {error}"
            logger.info(error)
            return None
    except Exception as e:
        logger.error(f"Unexpected error while upload profile pic on s3: {e}")
        raise e

def _check_user_agent_access(user_id, agent_int_uid):
    try:
        agent_privileges = _get_privileges_by_user_for_agent(user_id, agent_int_uid)
        logger.info(f"Agent Privileges: {agent_privileges}")
        if not agent_privileges:
            raise Exception("Function Error: User does not have access to the agent.")
        return agent_privileges
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error

def _create_agent_ai_name(agent_id, user_id):
    agent_data = _get_agent_details(agent_id)
    logger.info(agent_data)
    agent_privileges = _get_agent_privileges_by_user(user_id)
    agent_names = []
    for privilege in agent_privileges:
        if privilege.get("is_active", True) and not privilege.get("is_deleted", False):
            agent_int_uid = privilege.get("agent_int_uid")
            agent_details = _get_details_for_agentintuid(agent_int_uid)
            agent_name = agent_details.get("agent_name", "Unknown")
            if agent_name != "Unknown":
                agent_names.append(agent_name)
    exclude_name = ''
    if agent_names:
        exclude_name = ', '.join(agent_names)
    system_prompt = f"""Give one random name of a person, excluding {exclude_name}. Reply with only the name, no explanation. The generated name should not have any indication of race, color, creed and origin. Only first name is enough"""
    logger.info(f"system_prompt  {system_prompt}")
    ai_response = _get_ai_response({"prompt": system_prompt})
    logger.info(f"AI Name {ai_response}")
    return ai_response

def _save_mda_default_sections(agent_int_uid):
    try:
        mda_default_sections = _scan_table_with_filter({"table_name": "mda_section_report_map_default"})
        logger.info(f"MDA Default Sections: {mda_default_sections}")
        if not mda_default_sections:
            raise Exception("Function Error: MD&A Default Sections not found.")
        if mda_default_sections:
            for section in mda_default_sections:
                try:
                    item = {
                        "agent_int_uid_secid": f"{agent_int_uid}-{section['section_id']}",
                        "agent_int_uid": agent_int_uid,
                        "section_order": section['section_order'],
                        "instruction": section['instruction'],
                        "report_data": section['report_data'],
                        "section_title": section['section_title']
                    }
                    agent_mda_sections_table.put_item(Item=item)
                except Exception as error:
                    logger.error(f"Function Error: Unexpected error While Saving MDA Section data: {error}")
                    raise Exception(f"Function Error: Unexpected error While Saving MDA Section data: {error}")
        return True
    except Exception as e:
        logger.error(f"Unexpected error While Saving MDA Section data: {e}")
        raise e


def _create_securellm_agent_if_needed(user, env):
    user_agents = _get_agent_privileges_by_user(user["user_id"])
    for agent in user_agents:
        if agent.get("agent_int_uid", "").startswith("000"):
            agent_int_uid = agent["agent_int_uid"]
            agent_details = _get_details_for_agentintuid(agent_int_uid)
            bucket_name = f"{BUCKET_NAME}-{env}"
            presigned_url = _get_presigned_url(bucket_name, agent_details["profile_pic"], 3600) \
                            if agent_details.get("profile_pic") else None
            return {
                "agent_int_uid": agent_int_uid,
                "agent_name": agent_details.get("agent_name"),
                "profile_pic_url": presigned_url
            }
    agent_id = "000"
    int_id = "00000000"
    agent_int_uid = _get_agent_int_uid(agent_id, int_id)
    agent_name = _create_agent_ai_name(agent_id, user["user_id"])
    agent_data = _get_agent_details(agent_id)
    agent_pic = _generate_avatar_prompt(agent_name)
    s3_path = _save_agent_pic(agent_pic, agent_name, agent_int_uid, env, agent_data["agent_type"])
    bucket_name = f"{BUCKET_NAME}-{env}"
    presigned_url = _get_presigned_url(bucket_name, s3_path, 3600) if s3_path else None

    _create_record_agent_by_int(
        int_id, agent_int_uid, agent_name,
        agent_data["agent_type"], agent_data["skillset"],
        agent_data["welcome_prompt"], s3_path
    )
    agent_privilege_id = _get_agent_privilege_id()
    _create_agent_privilege_record(agent_privilege_id, agent_int_uid,agent_data["agent_persona"], user["user_id"], agent_data["llm_id"])
    return {
        "agent_int_uid": agent_int_uid,
        "agent_name": agent_name,
        "profile_pic_url": presigned_url
    }

def _get_tone_modifiers(user_id,agent_int_uid):
    try:
        agent_details = _get_privileges_by_user_for_agent(user_id,agent_int_uid)
        logger.info(f"Agent details  : {agent_details}")
        if not isinstance(agent_details, list) or not agent_details:
           return ""
        agent = agent_details[0]
        persona = agent.get("agent_persona", {})
        if not isinstance(persona, dict) or not persona:
            return ""
        # Normalize keys
        behaviour_keys = {key.strip().lower(): value for key, value in persona.items()}
        tone_parts = []
        if "casual" in behaviour_keys:
            tone_parts.append("Adopt an informal and relatable tone, similar to a colleague's conversation")
        if "friendly" in behaviour_keys:
            tone_parts.append("Sound warm and approachable while remaining respectful tone in explanations")
        if "consice" in behaviour_keys or "concise" in behaviour_keys:  # Handle typo
            tone_parts.append("Be brief and be clear and to the point, avoiding unnecessary elaboration")
        if "polished" in behaviour_keys:
            tone_parts.append("Ensure the language is refined, articulate, and professionally worded")
        if "professional" in behaviour_keys:
            tone_parts.append("Maintain a formal and business-appropriate tone throughout the response")
        if "descriptive" in behaviour_keys:
            tone_parts.append("Offer vivid and detailed explanations to clarify complex ideas, highlighting nuances and context")
        final_sentence = ", ".join(tone_parts[:-1])
        final_sentence += f", and {tone_parts[-1]}."
        return final_sentence
    except Exception as error:
        logger.error(f"Error while getting tone of agent: {error}")
        raise Exception(f"Function Error: Error while getting tone of agent: {error}")