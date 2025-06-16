import jwt, urllib, json, logging
from datetime import datetime, timezone, timedelta
import http.client
from urllib.parse import urlencode

# import from bez functions
from bez_utility.bez_metadata_users import _get_user_by_email, _create_user
from bez_utility.bez_utils_aws import _update_data_in_table
from bez_utility.bez_metadata_sessions import _create_session
from bez_utility.bez_metadata_agents import _create_securellm_agent_if_needed

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _get_auth0_access_token(data):
    config = data.get("config", "")
    logger.info(f"config: {config}")
    try:
        url = f"{config['AUTH0_DOMAIN']}"
        conn = http.client.HTTPSConnection(url)
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        request_body = {
            'grant_type': 'client_credentials',
            'client_id': config["AUTH0_CLIENT_ID"],
            "client_secret": config["AUTH0_CLIENT_SECRET"],
            'audience': f"https://{config['AUTH0_DOMAIN']}/api/v2/"}
        body = urlencode(request_body)
        conn.request("POST", "/oauth/token", body=body, headers=headers)
        response = conn.getresponse()
        response_data = response.read().decode()
        logger.info(f'Response: {response}')
        if response.status == 200:
            access_token = json.loads(response_data)['access_token']
            logger.info(f"access_token: {access_token}")
        else:
            raise Exception(f"Failed to get access token: {response_data}")
        return access_token
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": f"Unexpected error: {str(e)}"}

def _get_user_by_email_auth0(data):
    config = data.get("config", "")
    email = data.get("email", "")
    access_token = _get_auth0_access_token(data)
    logger.info(f"access_token: {access_token}")
    try:
        url = f"{config['AUTH0_DOMAIN']}"
        print(url)
        conn = http.client.HTTPSConnection(url)
        headers = {'Authorization': f'Bearer {access_token}',
                   'Accept': 'application/json'}
        params = urllib.parse.urlencode({'email': email})
        # Make the GET request to the Auth0 Management API to retrieve user by email
        conn.request("GET", f"/api/v2/users-by-email?{params}", headers=headers)
        # Get the response
        user_response = conn.getresponse()
        # Read and parse the response data
        data = user_response.read()
        user = json.loads(data.decode("utf-8"))
        logger.info(f"user: {user}")
        if user_response.status == 200:
            logger.info(f"user retrieved by email: {user}")
            return user
        else:
            print("Error:", user_response.status)
            print("Response :", user)
            raise Exception(f"Failed to get user by email: {user}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": f"Unexpected error: {str(e)}"}

def _get_user_token(email, password, config):
    try:
        conn = http.client.HTTPSConnection(config['AUTH0_DOMAIN'])
        headers = {'content-type': "application/x-www-form-urlencoded"}
        data = {
            'grant_type': 'http://auth0.com/oauth/grant-type/password-realm',
            'username': email,
            'password': password,
            'client_id': config['AUTH0_CLIENT_ID'],
            'client_secret': config['AUTH0_CLIENT_SECRET'],
            'realm': config['AUTH0_DATABASE'],  # Optional
            'scope': 'openid profile email',  # You can modify the scope
        }
        body = urlencode(data)
        conn.request("POST", "/oauth/token", body=body, headers=headers)
        response = conn.getresponse()
        response_data = response.read().decode()
        logger.info(json.loads(response_data))
        return {"status": response.status, "data": json.loads(response_data)}
    except Exception as e:
        logger.error(f"Error fetching user token: {e}")
        return {"error": str(e)}

def _get_jwt_info(id_token, config):
    print(id_token)
    jwks_url = f"https://{config['AUTH0_DOMAIN']}/.well-known/jwks.json"
    with urllib.request.urlopen(jwks_url) as response:
        jwks = json.loads(response.read().decode())
    # logger.info(f"jwks: {jwks}")
    # Extract public key
    public_keys = {key["kid"]: key for key in jwks["keys"]}
    header = jwt.get_unverified_header(id_token)
    logger.info(f"header: {header}")
    key = public_keys.get(header["kid"])
    json_key = json.dumps(key)
    logger.info(f"key: {json_key}")

    # Verify token
    if json_key:
        # logger.info(f"key: {json.loads(key)}")
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json_key)
        logger.info(f"public_key: {public_key}")
        payload = jwt.decode(id_token, public_key, algorithms='RS256', audience=config['AUTH0_CLIENT_ID'])
        logger.info(f"payload: {payload}")
        return payload
    else:
        return None

def _encode_token(data, config):
    data.update({"exp": datetime.now(tz=timezone.utc) + timedelta(seconds=24 * 60 * 60)})
    token = jwt.encode(data, config['SECRET_KEY'], "HS256")
    return token

def _create_jwt_token(data):
    try:
        token = data.get("token", "")
        config = data.get("config", "")
        env = data.get("env", "dev")
        logger.info(f"token: {token}")
        jwt_info = _get_jwt_info(token, config)
        logger.info(f"jwt_info: {jwt_info}, type of jwt_info: {type(jwt_info)}")
        if not jwt_info:
            return {"error": "Invalid token"}
        # Check if user already exists
        user = _get_user_by_email({"email": jwt_info.get("email")})
        if isinstance(user, list) and user:
            user = user[0]
        logger.info(f"user: {user}")
        if not user:
            name = jwt_info['name'].split(' ')
            logger.info(f"name: {name}")
            if len(name) == 2:
                first_name, last_name = tuple(name)
            else:
                first_name, last_name = name[0], ""
            user = _create_user({"auth0_id": jwt_info['sub'],
                                 "email": jwt_info['email'],
                                 "first_name": first_name,
                                 "last_name": last_name})
            user = _get_user_by_email({"email": jwt_info.get("email")})
            if isinstance(user, list) and user:
                user = user[0]
        elif not user["email_verified"] and jwt_info['email_verified']:
            update_user = _update_data_in_table({"table_name": "users", "key": "user_id", "key_value": user["user_id"],
                                                 "update_data": {"email_verified": True}})
        if not user["auth0_id"]:
            update_user = _update_data_in_table({"table_name": "users", "key": "user_id", "key_value": user["user_id"],
                                                 "update_data": {"auth0_id": jwt_info['sub']}})
        session_id = _create_session({"user_id": user["user_id"]})
        logger.info(f"Session ID returned: {session_id}")
        token_data = {"user_id": user["user_id"],
                      "session_id": session_id}
        token = _encode_token(token_data, config)
        result = {"token": token.decode('utf-8')}
        agent_info = _create_securellm_agent_if_needed(user, env)
        result.update(agent_info)
        return result
    except Exception as e:
        logger.error(f"Error creating JWT token: {e}")
        return {"error": f"Error creating JWT token: {str(e)}"}

def _generate_otp(config, mfa_token):
    try:
        conn = http.client.HTTPSConnection(config['AUTH0_DOMAIN'])
        headers = {'authorization': f'Bearer {mfa_token}', 'content-type': 'application/json'}
        conn.request("GET", "/mfa/authenticators", headers=headers)
        mfa_response = conn.getresponse()
        mfa_active = True
        mfa_response_data = mfa_response.read().decode("utf-8")
        if mfa_response.status == 200:
            mfa_active = any(
                [mfa.get('active') for mfa in json.loads(mfa_response_data) if mfa.get('authenticator_type') == 'otp'])
            results = {"data": {"mfa_required": True, "mfa_token": mfa_token, "mfa_active": mfa_active}}
            logger.info(f'MFA Results: {results}')
            return {
                'statusCode': 200,
                'body': json.dumps(results)
            }
        else:
            return {
                'statusCode': 400,
                'body': json.dumps("Something went wrong. Please try again later.")
            }
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"error": str(e)}

def _add_mfa(config, mfa_token):
    try:
        url = f"{config['AUTH0_DOMAIN']}"
        conn = http.client.HTTPSConnection(url)
        headers = {'authorization': f'Bearer {mfa_token}', 'content-type': 'application/json'}
        data = json.dumps({"client_id": config["AUTH0_CLIENT_ID"],
            "client_secret": config["AUTH0_CLIENT_SECRET"],
            "authenticator_types": ["otp"]})
        conn.request("POST", "/mfa/associate", body=data, headers=headers)
        response = conn.getresponse()
        logger.info(f'Response: {response}')
        return response
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": f"Unexpected error: {str(e)}"}

def _send_user_verification_email(user_id: str, config):
    try:
        access_token = _get_auth0_access_token({"config": config})
        logger.info(f"Access token from Auth0: {access_token}")
        conn = http.client.HTTPSConnection(config['AUTH0_DOMAIN'])
        headers = {'Content-Type': 'application/json',
                   'Accept': 'application/json',
                   'Authorization': f'Bearer {access_token}', }
        payload = json.dumps({
            "user_id": user_id,
            'client_id': config['AUTH0_CLIENT_ID']
        })
        conn.request("POST", "/api/v2/jobs/verification-email", body=payload, headers=headers)
        response = conn.getresponse()
        response_data = response.read().decode()
        logger.info(response.status)
        logger.info(f"Response from Auth0: {response_data}")
        return {"status": response.status, "data": json.loads(response_data)}
    except Exception as e:
        logger.info(f"Error sending verification email: {e}")
        return {"status": 500, "error": str(e)}

def _auth0_signup(email, password, first_name, last_name, config):
    try:
        url = f"{config['AUTH0_DOMAIN']}"
        conn = http.client.HTTPSConnection(url)
        headers = {"Content-Type": "application/json"}
        data = json.dumps({
            "client_id": config["AUTH0_CLIENT_ID"],
            "client_secret": config["AUTH0_CLIENT_SECRET"],
            "email": email,
            "password": password,
            "connection": config["AUTH0_DATABASE"],
            "name": f"{first_name} {last_name}",
            "user_metadata": {"client": "Bezi"}
        })    
        conn.request("POST", "/dbconnections/signup", body=data, headers=headers)
        response = conn.getresponse()
        if response.status == 200:
            response_data = response.read().decode()  
            response_json = json.loads(response_data) 
            return response_json
        elif response.status == 400:
            return {"error": "User already exists"}
        else:
            raise Exception(f"Auth0 Error: {response.text}")    
    except http.client.HTTPException as e:
        logger.error(f"HTTP error occurred: {e}")
        return {"error": "HTTPException", "message": str(e)}
    except ConnectionError as e:
        logger.error(f"Connection error: {e}")
        return {"error": "ConnectionError", "message": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": "Exception", "message": str(e)}    
    finally:
        conn.close()

def _verify_mfa(mfa_token, otp, config):
    try:
        conn = http.client.HTTPSConnection(config['AUTH0_DOMAIN'])
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'grant_type': 'http://auth0.com/oauth/grant-type/mfa-otp',
            "mfa_token": mfa_token,
            "otp": str(otp),
            'client_id': config['AUTH0_CLIENT_ID'],
                'client_secret': config['AUTH0_CLIENT_SECRET'],
                'realm': config['AUTH0_DATABASE'],  # Optional
                'scope': 'openid profile email'
        }
        logger.info(f"Data: {data}")
        body = urlencode(data)
        conn.request("POST", "/oauth/token", body=body, headers=headers)
        response = conn.getresponse()
        response_data = response.read().decode()
        logger.info(json.loads(response_data))
        return {"status": response.status, "data": json.loads(response_data)}
    except Exception as e:
        logger.error(f"Error verifying MFA: {e}")
        return False

def _get_user_mfa_factors(access_token, config, user_id):
    conn = http.client.HTTPSConnection(config['AUTH0_DOMAIN'])    
    headers = {
        'Authorization': f'Bearer {access_token}'
    }    
    conn.request("GET", f"/api/v2/users/{user_id}/authentication-methods", headers=headers)
    response = conn.getresponse()
    response_data = response.read()
    return {"status": response.status, "data": json.loads(response_data)}

def _delete_mfa_factor(access_token, mfa_factor_id, config, user_id):
    conn = http.client.HTTPSConnection(config['AUTH0_DOMAIN'])    
    headers = {
        'Authorization': f'Bearer {access_token}'
    }    
    conn.request("DELETE", f"/api/v2/users/{user_id}/authentication-methods/{mfa_factor_id}", headers=headers)    
    response = conn.getresponse()
    response_data = response.read()    
    return {"status": response.status, "data": response_data}