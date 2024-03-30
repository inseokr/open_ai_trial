import requests
import json
import os
import certifi
import jwt
import base64

def get_access_token(username, password, login, url):
    """ Function to authenticate and receive access token from the server. """
    url_r = f"{url}/{login}"
    js =  {"username": username, 
           "password": password, 
           "reportLoginResult": "true"}
    print (url_r)
    response = requests.post(url_r,json = js)
    if response.status_code == 200:
        return response.json()
    else:
        print (response.status_code, response.json())
        raise Exception("Failed to authenticate")
    return

def test_ls_get (route, url, params = {}, token = ''):
    """ Function to access unprotected and protected route using the JWT token. """
    url = f'{url}/{route}'
    print (f'url: {url}')
    headers = {'Authorization': f'Bearer {token}'}
    rsp = requests.get(url, params = params, headers = headers, verify=certifi.where())
    print(rsp.status_code)
    try:
        print(json.dumps(rsp.json()))
    except Exception as e:
        print(str(e))
    return rsp

def test_ls_post (data_out: dict, route: str, url, token = '', output = 'txt', target = 'agent')-> str:
    headers = {
    "Content-Type": "application/json",
    'Authorization': f'Bearer {token}'
    }
    url = f'{url}/{route}'
    response = requests.post(url, json=data_out, headers=headers)
    print (response)
    if response.status_code == 200:
        data = response.json()
        if target == 'agent':
            answer = data.get('answer', 'No answer received')
            if output == 'txt':
                return f"Answer: {answer}"
            else:
                return answer
        else:
            return data
    else:
        print (response.status_code, response.json())
        raise Exception("Failed to authenticate")
    return
    
def decode_jwt(token):
    header, payload, signature = token.split('.')
    header_decoded = base64.urlsafe_b64decode(add_padding(header)).decode('utf-8')
    payload_decoded = base64.urlsafe_b64decode(add_padding(payload)).decode('utf-8')

    return {
        "header": json.loads(header_decoded),
        "payload": json.loads(payload_decoded),
        "signature": signature
    }

def add_padding(str):
    """Adds padding to the Base64 encoded string to make it valid."""
    return str + '=' * (4 - len(str) % 4)
