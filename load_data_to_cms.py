import json
from api_handler import create_file, create_product, link_main_image
from get_access_token import get_access_token
from dotenv import load_dotenv
import os


if __name__ == '__main__':
    load_dotenv()
    el_path_client_id = os.getenv('ELASTICPATH_CLIENT_ID')
    el_path_client_secret = os.getenv('ELASTICPATH_CLIENT_SECRET')
    access_token = get_access_token(el_path_client_id, el_path_client_secret).get('access_token')
    with open('./data/menu.json', 'r') as file:
        products = json.load(file)
    for product in products:
        try:
            product_id = create_product(product, access_token)['data']['id']
            image_id = create_file(product, access_token)['data']['id']
            link_main_image(product_id, image_id, access_token)
        except Exception as err:
            # fix, make logging
            print(err)
