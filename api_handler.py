import requests
import os
from pathlib import Path
from googletrans import Translator
from geopy import distance


def get_all_products(access_token: str):
    url = 'https://api.moltin.com/v2/products'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_product(product_id: str, access_token: str):
    url = f'https://api.moltin.com/v2/products/{product_id}'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'X-MOLTIN-CURRENCY': 'RUB'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def add_product_to_card(
    card_id: str,
    product_id: str,
    access_token: str,
    quantity: int
) -> None:
    url = f'https://api.moltin.com/v2/carts/{card_id}/items'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    payload = {
        'data': {
            'id': product_id,
            'type': 'cart_item',
            'quantity': quantity,
        },
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()


def get_card(card_id: str, access_token: str):
    url = f'https://api.moltin.com/v2/carts/{card_id}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_card_items(card_id: str, access_token: str):
    url = f'https://api.moltin.com/v2/carts/{card_id}/items'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_image(image_id: str, access_token: str):
    url = f'https://api.moltin.com/v2/files/{image_id}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    file_url = response.json().get('data').get('link').get('href')
    response = requests.get(file_url)
    response.raise_for_status()
    _, image_name = os.path.split(file_url)
    path = os.path.join(os.getcwd(), 'store_images')
    Path(path).mkdir(parents=True, exist_ok=True)
    named_path = os.path.join(path, image_name)
    with open(named_path, 'wb') as file:
        file.write(response.content)
    return named_path


def remove_cart_item(card_id: str, product_id: str, access_token: str) -> None:
    url = f'https://api.moltin.com/v2/carts/{card_id}/items/{product_id}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.delete(url, headers=headers)
    response.raise_for_status()


def create_customer(
    phone: str,
    email: str,
    password: str,
    access_token: str
) -> None:
    url = 'https://api.moltin.com/v2/customers'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    payload = {
        'data': {
            'type': 'customer',
            'name': phone,
            'email': email,
            'password': password,
        },
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()


def make_slug(product_name):
    translator = Translator()
    translated_text = translator.translate(product_name, src='ru').text
    chunked_text = translated_text.split(' ')
    slug_text = '-'.join(chunked_text).lower()
    return slug_text


def create_product(product, access_token):
    url = 'https://api.moltin.com/v2/products'
    headers = {
        'Authorization': f'Bearer {access_token}',
        }
    product_id = product['id']
    product_name = product['name']
    product_description = f"{product['description']}, содержание: жиры {product['food_value']['fats']}г,\
белки {product['food_value']['proteins']}г, углеводы {product['food_value']['carbohydrates']}г,\
каллорийность {product['food_value']['kiloCalories']} ккал, вес {product['food_value']['weight']}г"
    product_price = product['price']
    payload = {
        'data': {
            'type': 'product',
            'name': product_name,
            'slug': make_slug(product_name),
            'sku': str(product_id),
            'manage_stock': False,
            'description': product_description,
            'price': [
                {
                    'amount': product_price,
                    'currency': 'RUB',
                    'includes_tax': True,
                    }
                ],
            'status': 'live',
            'commodity_type': 'physical'
            },
        }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


def create_file(product, access_token):
    '''file creation'''
    url = 'https://api.moltin.com/v2/files'
    headers = {
        'Authorization': f'Bearer {access_token}'
        }

    files = {
            'file_location': (None, product['product_image']['url']),
        }
    response = requests.post(url, headers=headers, files=files)
    response.raise_for_status()
    return response.json()


def link_main_image(product_id, image_id, access_token):
    url = f'https://api.moltin.com/v2/products/{product_id}/relationships/main-image'
    headers = {
        'Authorization': f'Bearer {access_token}'
        }
    payload = {
        'data': {
            'type': 'main_image',
            'id': image_id
            },
        }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()


def create_flow(
    name,
    description,
    access_token,
    enabled=True
        ):
    url = 'https://api.moltin.com/v2/flows'
    headers = {
        'Authorization': f'Bearer {access_token}'
        }
    payload = {
        'data': {
            'type': 'flow',
            'name': name,
            'slug': name.lower(),
            'description': description,
            'enabled': enabled
            }
        }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


def create_flows_field(
    flow_id,
    field_name,
    field_type,
    description,
    access_token,
    required=True,
    enabled=True,
        ):
    url = 'https://api.moltin.com/v2/fields'
    headers = {
        'Authorization': f'Bearer {access_token}'
        }
    payload = {
        'data': {
            'type': 'field',
            'name': field_name,
            'slug': field_name.lower(),
            'field_type': field_type,
            'description': description,
            'required': required,
            'enabled': enabled,
            'relationships': {
                'flow': {
                    'data': {
                        'type': 'flow',
                        'id': flow_id
                    }
                }
            }
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


def create_entry(
    flow_slug,
    address_slug,
    address_value,
    alias_slug,
    alias_value,
    lat_slug,
    lat_value,
    lon_slug,
    lon_value,
    access_token
        ):
    url = f'https://api.moltin.com/v2/flows/{flow_slug}/entries'
    headers = {
        'Authorization': f'Bearer {access_token}'
        }
    payload = {
        'data': {
            'type': 'entry',
            f'{address_slug}': f'{address_value}',
            f'{alias_slug}': f'{alias_value}',
            f'{lat_slug}': f'{lat_value}',
            f'{lon_slug}': f'{lon_value}'
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()


def fetch_coordinates(apikey, address):
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = requests.get(base_url, params={
        "geocode": address,
        "apikey": apikey,
        "format": "json",
    })
    response.raise_for_status()
    found_places = response.json()['response']['GeoObjectCollection']['featureMember']
    if not found_places:
        return None
    most_relevant = found_places[0]
    #yandex_address = most_relevant['GeoObject']['Point']['pos']
    #print(most_relevant)
    return most_relevant


def get_distance(coordinates, restaurant_coordinates):
    lon, lat = coordinates
    restaurant_lon, restaurant_lat = restaurant_coordinates
    if lon and lat and restaurant_lon and restaurant_lat is not None:
        return distance.distance(coordinates, restaurant_coordinates).km


def get_all_entries(access_token, flow_slug):
    url = f'https://api.moltin.com/v2/flows/{flow_slug}/entries'
    headers = {
        'Authorization': f'Bearer {access_token}'
        }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def create_entry_customer(
    lat_slug,
    lat_value,
    lon_slug,
    lon_value,
    access_token
        ):
    url = f'https://api.moltin.com/v2/flows/customer_address/entries'
    headers = {
        'Authorization': f'Bearer {access_token}'
        }
    payload = {
        'data': {
            'type': 'entry',
            f'{lat_slug}': f'{lat_value}',
            f'{lon_slug}': f'{lon_value}'
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
