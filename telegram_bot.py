import logging
import os
import time
from functools import partial

import redis
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (CallbackContext, CallbackQueryHandler,
                          CommandHandler, ConversationHandler, Filters,
                          MessageHandler, Updater)
from api_handler import (add_product_to_card, create_customer,
                         get_all_products, get_card, get_card_items, get_image,
                         get_product, remove_cart_item)
from get_access_token import get_access_token
from logging_handler import TelegramLogsHandler
from storing_data import PizzaShopPersistence
import math

logger = logging.getLogger(__name__)

START, HANDLE_MENU, HANDLE_DESCRIPTION,\
    HANDLE_CART, WAITING_EMAIL, CLOSE_ORDER = range(6)


def update_token(func):
    def inner(elastickpath_access_token, client_id_secret, update: Update, context: CallbackContext):
        epoch_time = elastickpath_access_token.get('expires')
        el_path_client_id, el_path_client_secret = client_id_secret
        if time.time() > epoch_time:
            elastickpath_access_token = get_access_token(el_path_client_id, el_path_client_secret)
        return func(elastickpath_access_token, client_id_secret, update, context)
    return inner


def create_menu(products, page=0):
    keyboard = []
    product_on_page = 5
    max_products = math.ceil(len(products.get('data'))/product_on_page)*product_on_page
    for count, product in enumerate(products.get('data')):
        if page+product_on_page > count and count >= page:
            product_name = product.get('name')
            product_id = product.get('id')
            button = [InlineKeyboardButton(product_name, callback_data=product_id)]
            keyboard.append(button)
    card_keyboard = [InlineKeyboardButton('Корзина', callback_data='productcard')]
    if page <= 0:
        incr_page = page + product_on_page
        navigation_keyboard = [
            InlineKeyboardButton('След',  callback_data=f'pagenext#{incr_page}')
        ]
    elif page >= max_products:
        decr_page = page - product_on_page
        navigation_keyboard = [
            InlineKeyboardButton('Пред',  callback_data=f'pageback#{decr_page}')
        ]
    else:
        incr_page = page + product_on_page
        decr_page = page - product_on_page
        navigation_keyboard = [
            InlineKeyboardButton('След',  callback_data=f'pagenext#{incr_page}'),
            InlineKeyboardButton('Пред',  callback_data=f'pageback#{decr_page}')
        ]
    keyboard.append(navigation_keyboard)
    keyboard.append(card_keyboard)
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup


@update_token
def start(elastickpath_access_token, client_id_secret, update: Update, context: CallbackContext) -> None:
    products = get_all_products(elastickpath_access_token.get('access_token'))
    update.message.reply_text(
        'Пожалуйста выберите товар',
        reply_markup=create_menu(products)
        )
    return HANDLE_DESCRIPTION


@update_token
def handle_description(
    elastickpath_access_token,
    client_id_secret,
    update: Update,
    context: CallbackContext
):
    message_id = update.effective_message.message_id
    chat_id = update.effective_message.chat_id
    query = update.callback_query
    context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    product_id = query.data
    access_token = elastickpath_access_token.get('access_token')
    product_payload = get_product(product_id, access_token)
    product_name = product_payload.get('data').get('name')
    product_price = product_payload.get('data').get('meta').get('display_price').get('with_tax').get('formatted')
    product_price_formatted = product_price.strip('RUB')
    product_text = product_payload.get('data').get('description')
    product_image_id = product_payload.get('data').get('relationships').get('main_image').get('data').get('id')
    path = get_image(product_image_id, access_token)
    product_describtion = f'{product_name}\n{product_price_formatted} рублей\n\n{product_text}'
    keyboard = [
        [
            InlineKeyboardButton('Добавить 1 пиццу в корзину', callback_data=f'{product_id}|card:1'),
            InlineKeyboardButton('Добавить 2 пиццы в корзину', callback_data=f'{product_id}|card:2')
            ],
        [InlineKeyboardButton('Корзина', callback_data='productcard')],
        [InlineKeyboardButton('Назад', callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    with open(path, 'rb') as file:
        context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=file,
            caption=product_describtion,
            reply_markup=reply_markup
            )
    return HANDLE_MENU


@update_token
def handle_product_button(
    elastickpath_access_token,
    client_id_secret,
    update: Update,
    context: CallbackContext
):
    chat_id = update.effective_message.chat_id
    query = update.callback_query
    access_token = elastickpath_access_token.get('access_token')
    product_id, card = query.data.split('|')
    _, quantity = card.split(':')
    add_product_to_card(chat_id, product_id, access_token, int(quantity))
    update.callback_query.answer(text='Товар добавлен в корзину')
    return HANDLE_MENU


@update_token
def handle_menu(elastickpath_access_token, client_id_secret, update: Update, context: CallbackContext) -> None:
    access_token = elastickpath_access_token.get('access_token')
    products = get_all_products(access_token)
    message_id = update.effective_message.message_id
    chat_id = update.effective_message.chat_id
    query = update.callback_query
    page = 0
    if 'pagenext' in query.data or 'pageback' in query.data:
        button, page = query.data.split('#')
    context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    context.bot.send_message(
        chat_id=chat_id,
        text='Пожалуйста выберите товар',
        reply_markup=create_menu(products, int(page))
        )
    return HANDLE_DESCRIPTION


@update_token
def handle_cart(elastickpath_access_token, client_id_secret, update: Update, context: CallbackContext):
    chat_id = update.effective_message.chat_id
    access_token = elastickpath_access_token.get('access_token')
    cards = get_card(chat_id, access_token)
    card_items = get_card_items(chat_id, access_token)
    card_total_price = cards.get('data').get('meta').get('display_price').get('with_tax').get('formatted').strip('RUB')
    message_id = update.effective_message.message_id
    chat_id = update.effective_message.chat_id
    context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    products_list = []
    keyboard = []
    for item in card_items.get('data'):
        card_item_id = item.get('id')
        item_name = item.get('name')
        item_quantity = item.get('quantity')
        item_price_per_item = item.get('meta').get('display_price').get('with_tax').get('unit').get('formatted').strip('RUB')
        item_total_price = item.get('meta').get('display_price').get('with_tax').get('value').get('formatted').strip('RUB')
        products_describtion = f'{item_name}\n{item_price_per_item}руб за шт\n{item_quantity}шт в корзине за {item_total_price}руб\n\n'
        products_list.append(products_describtion)
        button = [InlineKeyboardButton(f'Убрать из корзины {item_name}', callback_data=card_item_id)]
        keyboard.append(button)
    back_button = [InlineKeyboardButton('Назад', callback_data='back')]
    keyboard.append(back_button)
    pay_button = [InlineKeyboardButton('Оплатить', callback_data='paybutton')]
    keyboard.append(pay_button)
    reply_markup = InlineKeyboardMarkup(keyboard)
    all_products = ''.join(product for product in products_list)
    card_message = f'{all_products}\nИтого:{card_total_price}руб'
    context.bot.send_message(
        chat_id=chat_id,
        text=card_message,
        reply_markup=reply_markup
    )
    return HANDLE_CART


def remove_card_item(elastickpath_access_token, client_id_secret, update: Update, context: CallbackContext):
    chat_id = update.effective_message.chat_id
    query = update.callback_query
    product_id = query.data
    access_token = elastickpath_access_token.get('access_token')
    update.callback_query.answer(text='Товар удален из корзины')
    remove_cart_item(card_id=chat_id, product_id=product_id, access_token=access_token)
    handle_cart(elastickpath_access_token, client_id_secret, update, context)
    return HANDLE_CART


def handle_pay_request(redis_db, update: Update, context: CallbackContext):
    message_id = update.effective_message.message_id
    chat_id = update.effective_message.chat_id
    context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    message = 'Пришлите пожалуйста ваш email'
    context.bot.send_message(
        chat_id=chat_id,
        text=message,
    )
    return WAITING_EMAIL


def handle_pay_request_phone(redis_db, update: Update, context: CallbackContext):
    chat_id = update.effective_message.chat_id
    email = update.message.text
    chat_id_redis = f'{chat_id}_email'
    redis_db.set(chat_id_redis, email)
    message = 'Пришлите пожалуйста ваш телефонный номер'
    context.bot.send_message(
        chat_id=chat_id,
        text=message,
    )
    return CLOSE_ORDER


def close_order(
    redis_db,
    elastickpath_access_token,
    client_id_secret,
    update: Update,
    context: CallbackContext
):
    chat_id = update.effective_message.chat_id
    chat_id_redis_email = f'{chat_id}_email'
    email = redis_db.get(chat_id_redis_email).decode('utf-8')
    password = '12345'
    phone = update.message.text
    access_token = elastickpath_access_token.get('access_token')
    create_customer(
        phone,
        email,
        password,
        access_token)
    message = f'Ваш email:{email}\nВаш телефон: {phone}'
    keyboard = [
        [
            InlineKeyboardButton('Да', callback_data='yes'),
            InlineKeyboardButton('Нет', callback_data='no'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(
        chat_id=chat_id,
        text=message,
        reply_markup=reply_markup
    )
    return CLOSE_ORDER


def handle_error(update: Update, context: CallbackContext):
    """Log Errors caused by Updates."""
    logger.warning(
        f'Update {update} caused error {context.error},\
        traceback {context.error.__traceback__}'
        )


def end_conversation(update: Update, context: CallbackContext):
    update.message.reply_text(
        'Пока!'
        )
    return ConversationHandler.END


def main():
    load_dotenv()
    token = os.getenv('TOKEN_TELEGRAM')
    user_id = os.getenv('TG_USER_ID')
    redis_host = os.getenv('REDIS_HOST')
    redis_port = os.getenv('REDIS_PORT')
    redis_pass = os.getenv('REDIS_PASS')
    el_path_client_id = os.getenv('ELASTICPATH_CLIENT_ID')
    el_path_client_secret = os.getenv('ELASTICPATH_CLIENT_SECRET')
    elastickpath_access_token = get_access_token(el_path_client_id, el_path_client_secret)
    client_id_secret = (el_path_client_id, el_path_client_secret)
    redis_base = redis.Redis(
        host=redis_host,
        port=redis_port,
        password=redis_pass
        )
    persistence = PizzaShopPersistence(redis_base)
    logging_token = os.getenv('TG_TOKEN_LOGGING')
    logging_bot = Bot(token=logging_token)
    logging.basicConfig(
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
    logger.setLevel(logging.DEBUG)
    logger.addHandler(TelegramLogsHandler(tg_bot=logging_bot, chat_id=user_id))
    logger.info('Pizza store bot запущен')
    """Start the bot."""
    updater = Updater(token, persistence=persistence)
    dispatcher = updater.dispatcher
    partial_start = partial(start, elastickpath_access_token, client_id_secret)
    partial_handle_menu = partial(handle_menu, elastickpath_access_token, client_id_secret)
    partial_handle_describtion = partial(handle_description, elastickpath_access_token, client_id_secret)
    partial_handle_cart = partial(handle_cart, elastickpath_access_token, client_id_secret)
    partial_handle_product_button = partial(handle_product_button, elastickpath_access_token, client_id_secret)
    partial_remove_card_item = partial(remove_card_item, elastickpath_access_token, client_id_secret)
    partial_handle_pay_request = partial(handle_pay_request, redis_base)
    partial_handle_pay_request_phone = partial(handle_pay_request_phone, redis_base)
    partial_close_order = partial(close_order, redis_base, elastickpath_access_token, client_id_secret)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", partial_start)],
        states={
            START: [
                MessageHandler(Filters.text, partial_start),
                ],
            HANDLE_DESCRIPTION: [
                CallbackQueryHandler(partial_handle_product_button, pattern="^(\S{3,}card:[1-2])$"),
                CallbackQueryHandler(partial_handle_menu, pattern="^(pagenext#\d+)$"),
                CallbackQueryHandler(partial_handle_menu, pattern="^(pageback#\d+)$"),
                CallbackQueryHandler(partial_handle_menu, pattern="^(back)$"),
                CallbackQueryHandler(partial_handle_describtion),
                ],
            HANDLE_MENU: [
                CallbackQueryHandler(partial_handle_menu, pattern="^(back)$"),
                CallbackQueryHandler(partial_handle_product_button, pattern="^(\S{3,}card:[1-2])$"),
                CallbackQueryHandler(partial_handle_cart, pattern="^(productcard)$")
            ],
            HANDLE_CART: [
                CallbackQueryHandler(partial_handle_cart, pattern="^(productcard)$"),
                CallbackQueryHandler(partial_handle_pay_request, pattern="^(paybutton)$"),
                CallbackQueryHandler(partial_handle_menu, pattern="^(back)$"),
                CallbackQueryHandler(partial_remove_card_item)
            ],
            WAITING_EMAIL: [
                MessageHandler(
                    Filters.text & ~Filters.command,
                    partial_handle_pay_request_phone
                    ),
            ],
            CLOSE_ORDER: [
                CallbackQueryHandler(partial_handle_menu, pattern="^(yes)$"),
                CallbackQueryHandler(partial_handle_pay_request, pattern="^(no)$"),
                MessageHandler(Filters.text & ~Filters.command, partial_close_order),
            ]
        },
        fallbacks=[CommandHandler("end", end_conversation)],
        name="pizza_conversation",
        persistent=True
    )
    dispatcher.add_handler(conv_handler)
    dispatcher.add_error_handler(handle_error)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
