import requests
import os
from pathlib import Path


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
        'Authorization': f'Bearer {access_token}'
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
