import json, logging

# import from bez resources
from bez_utility.bez_metadata_agents import _get_agent_privileges_by_user, _get_details_for_agentintuid, _get_agent_details_by_status
from bez_utility.bez_utils_aws import _get_presigned_url
from bez_utility.bez_metadata_int import _get_int_by_intid
from bez_utility.bez_metadata_clients import _get_client_by_clientid

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

SORT_BY_MAP = {
    "Agent Name (A-Z)": "agent_name_asc",
    "Agent Name (Z-A)": "agent_name_desc",
    "Agent Type": "agent_type"
}


def _agent_list(event):
    try:
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        if not user_id:
            return {"statusCode": 400, "body": json.dumps({"error":"User Id is a required field. Please re-login to try again."})}
        if event.get('queryStringParameters'):
            query_params = event.get('queryStringParameters', {})
            sort_by_label = query_params.get('sort_by', "Agent Name (A-Z)")
        else:
            sort_by_label = "Agent Name (A-Z)"
        sort_by = SORT_BY_MAP.get(sort_by_label, "agent_name_asc")
        agents_hired = _agent_hired_list(event, sort_by)
        agents_to_hire = _agent_to_be_hired_list(event, sort_by)
        agents_coming_soon = _agents_coming_soon(event, sort_by)
        agent_list = []
        agent_list.append(agents_hired)
        agent_list.append(agents_to_hire)
        agent_list.append(agents_coming_soon)
        logger.info(f"Agent list: {agent_list}")
        return {
            "statusCode": 200,
            "body": json.dumps(agent_list)
        }
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error creating integrations info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }

def _agent_hired_list(event, sort_by):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        if not user_id:
            return {"statusCode": 400, "body": json.dumps({"error":"User Id is a required field. Please re-login to try again."})}
        env = event.get("headers", {}).get("env", "dev")
        agent_privileges = _get_agent_privileges_by_user(user_id)
        logger.info(f"Agent privileges: {agent_privileges}")
        
        if not agent_privileges:
            return {"statusCode": 400, "body": json.dumps({"error":"No agents are currently assigned to this user"})}
        
        agent = []
        for privilege in agent_privileges:
            agent_int_uid = privilege.get("agent_int_uid")
            try:
                agent_details = _get_details_for_agentintuid(agent_int_uid)
                logger.info(f"Agent details: {agent_details}")
                print(f"Agent details: {agent_details}")

                is_active = privilege.get("is_active", True)
                is_deleted = privilege.get("is_deleted", False)

                if not (is_active and not is_deleted):
                    continue

                integration_id = agent_details.get("int_id")
                integration = _get_int_by_intid(integration_id)

                if not integration:
                    logger.warning(f"Skipping agent_int_uid {agent_int_uid} due to missing integration for int_id {integration_id}")
                    continue
                profile_pic_key = agent_details.get("profile_pic", None)
                bucket_name = f"bez-{env}"
                presigned_url = _get_presigned_url(bucket_name, profile_pic_key, 3600) if profile_pic_key else None

                client_id = integration.get("client_id")
                if client_id:
                    client = _get_client_by_clientid(client_id)
                    if not client:
                        logger.warning(f"Client not found for client_id {client_id}, skipping agent_int_uid {agent_int_uid}")
                        continue
                    client_name = client.get("client_name", "Unknown")
                else:
                    client_name = "Unknown"

                print(f"Integration: {client_id}, client: {client}")

                agent.append({
                    "agent_int_uid": agent_details["agent_int_uid"],
                    "agent_id": agent_details["agent_int_uid"][:3],
                    "agent_type": agent_details.get("agent_type", "Unknown"),
                    "agent_name": agent_details.get("agent_name", "Unknown"),
                    "skillset": agent_details.get("skillset", "Unknown"),
                    "agent_status": "Hired",
                    "integration_name": integration.get("integration_name", "Unknown"),
                    "client_name": client_name,
                    "profile_pic_path": presigned_url
                })

            except Exception as e:
                logger.warning(f"Skipping agent_int_uid {agent_int_uid} due to error: {str(e)}")
                continue

        agent = _sort_agents(agent, sort_by)
        response_data = {"agent_hired": agent}
        logger.info(f"Response data: {response_data}")
        return response_data
    except Exception as e:
        raise e

def _agent_to_be_hired_list(event, sort_by):
    try:
        logger.info(f"Received event: {event}")
        agents_list = _get_agent_details_by_status("To Hire")
        logger.info(f"Agents list: {agents_list}")
        agents = [
            {
                "agent_id": agent.get("agent_id"),
                "agent_name": agent.get("agent_name"),
                "profile_pic": agent.get("profile_pic"),
                "agent_type": agent.get("agent_type"),
                "skillset": agent.get("skillset", "Unknown"),
                "agent_status": "To be Hired"
            }
            for agent in agents_list
        ]
        logger.info(agents)
        agents = _sort_agents(agents, sort_by)

        response_data = {"agents_to_hire": agents}
        return response_data
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise e

def _agents_coming_soon(event, sort_by):
    try:
        logger.info(f"Received event: {event}")
        agents_list = _get_agent_details_by_status("Coming Soon")
        logger.info(f"Agents list: {agents_list}")
        agents = [
            {
                "agent_id": agent.get("agent_id"),
                "agent_name": agent.get("agent_name"),
                "profile_pic": agent.get("profile_pic"),
                "agent_type": agent.get("agent_type"),
                "skillset": agent.get("skillset", "Unknown"),
                "agent_status": "Coming Soon"
            }
            for agent in agents_list
        ]
        logger.info(agents)
        agents = _sort_agents(agents, sort_by)
        response_data = {"agents_coming_soon": agents}
        return response_data
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise e

def _sort_agents(agent_list, sort_by):
    if sort_by == "agent_name_desc":
        return sorted(agent_list, key=lambda x: (x.get("agent_name") or "").lower(), reverse=True)
    elif sort_by == "agent_type":
        return sorted(agent_list, key=lambda x: x.get("agent_type", "").lower())
    else:  # Default to agent_name ascending
        return sorted(agent_list, key=lambda x: (x.get("agent_name") or "").lower())