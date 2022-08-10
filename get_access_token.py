import requests
from dotenv import load_dotenv
import os


def get_access_token(client_id: str, client_secret: str):
    url = 'https://api.moltin.com/oauth/access_token'
    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
        }
    r = requests.put(url=url, data=data)
    r.raise_for_status()
    token = r.json()
    return token


if __name__ == '__main__':
    load_dotenv()
    el_path_client_id = os.getenv('ELASTICPATH_CLIENT_ID')
    el_path_client_secret = os.getenv('ELASTICPATH_CLIENT_SECRET')
    print(get_access_token(el_path_client_id, el_path_client_secret))
