import json
from api_handler import create_file, create_product, link_main_image, create_flow, create_flows_field, create_entry
from get_access_token import get_access_token
from dotenv import load_dotenv
import os
from time import sleep

if __name__ == '__main__':
    load_dotenv()
    el_path_client_id = os.getenv('ELASTICPATH_CLIENT_ID')
    el_path_client_secret = os.getenv('ELASTICPATH_CLIENT_SECRET')
    access_token = get_access_token(el_path_client_id, el_path_client_secret).get('access_token')
    with open('./data/menu.json', 'r') as file:
        products = json.load(file)
    with open('./data/addresses.json', 'r') as file:
        addresses = json.load(file)
    flow_resp = create_flow(
        name='Pizzeria',
        description='Flow for pizzeria',
        access_token=access_token,
        )
    flow_id = flow_resp['data']['id']
    flow_slug = flow_resp['data']['slug']
    address_slug = create_flows_field(
        flow_id=flow_id,
        field_name='Address',
        field_type='string',
        description='Pizzeria addres',
        access_token=access_token
    )['data']['slug']
    alias_slug = create_flows_field(
        flow_id=flow_id,
        field_name='Alias',
        field_type='string',
        description='Alias in Russian',
        access_token=access_token
    )['data']['slug']
    long_slug = create_flows_field(
        flow_id=flow_id,
        field_name='Longitude',
        field_type='string',
        description='Longitude coordinates',
        access_token=access_token
    )['data']['slug']
    lat_slug = create_flows_field(
        flow_id=flow_id,
        field_name='Latitude',
        field_type='string',
        description='Latitude coordinates',
        access_token=access_token
    )['data']['slug']
    for product in products:
        try:
            product_id = create_product(product, access_token)['data']['id']
            image_id = create_file(product, access_token)['data']['id']
            link_main_image(product_id, image_id, access_token)
        except Exception as err:
            # fix, make logging
            print(err)
    for address in addresses:
        create_entry(
            flow_slug,
            address_slug,
            address['address']['full'],
            alias_slug,
            address['alias'],
            lat_slug,
            address['coordinates']['lat'],
            long_slug,
            address['coordinates']['lon'],
            access_token
        )
        sleep(2)
