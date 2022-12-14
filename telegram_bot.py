import logging
import math
import os
import time
from decimal import Decimal
from functools import partial
from re import sub

import redis
from dotenv import load_dotenv
from telegram import (Bot, InlineKeyboardButton, InlineKeyboardMarkup,
                      LabeledPrice, Update)
from telegram.ext import (CallbackContext, CallbackQueryHandler,
                          CommandHandler, ConversationHandler, Filters,
                          MessageHandler, PreCheckoutQueryHandler, Updater)

from api_handler import (add_product_to_card, fetch_coordinates,
                         get_all_entries, get_all_products, get_card,
                         get_card_items, get_distance, get_image, get_product,
                         remove_cart_item)
from get_access_token import get_access_token
from logging_handler import TelegramLogsHandler
from storing_data import PizzaShopPersistence

logger = logging.getLogger(__name__)

START, HANDLE_MENU, HANDLE_DESCRIPTION,\
    HANDLE_CART, WAITING_GEO, CLOSE_ORDER = range(6)


def update_token(func):
    def inner(elastickpath_access_token, client_id_secret, update: Update, context: CallbackContext):
        epoch_time = elastickpath_access_token.get('expires')
        el_path_client_id, el_path_client_secret = client_id_secret
        if time.time() > epoch_time:
            elastickpath_access_token = get_access_token(el_path_client_id, el_path_client_secret)
        return func(elastickpath_access_token, client_id_secret, update, context)
    return inner


def get_restaurant_distance(restaurant):
    return restaurant['distance']


def find_nearest_restaurant(coordinates, access_token):
    pizza_slug = 'pizzeria'
    all_restaurants_with_distance = []
    restaurants = get_all_entries(access_token, pizza_slug)
    for restuarant in restaurants['data']:
        restaurants_with_distance = {}
        restuarant_lon = restuarant['longitude']
        restuarant_lat = restuarant['latitude']
        restaurants_with_distance['restuarant'] = restuarant['address']
        restaurants_with_distance['distance'] = get_distance(coordinates, (restuarant_lon, restuarant_lat))
        restaurants_with_distance['coordinates'] = (restuarant_lon, restuarant_lat)
        restaurants_with_distance['user_coordinates'] = coordinates
        all_restaurants_with_distance.append(restaurants_with_distance)
    nearest_restaurant = min(all_restaurants_with_distance, key=get_restaurant_distance)
    return nearest_restaurant



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
    card_keyboard = [InlineKeyboardButton('??????????????', callback_data='productcard')]
    if page <= 0:
        incr_page = page + product_on_page
        navigation_keyboard = [
            InlineKeyboardButton('????????',  callback_data=f'pagenext#{incr_page}')
        ]
    elif page >= max_products:
        decr_page = page - product_on_page
        navigation_keyboard = [
            InlineKeyboardButton('????????',  callback_data=f'pageback#{decr_page}')
        ]
    else:
        incr_page = page + product_on_page
        decr_page = page - product_on_page
        navigation_keyboard = [
            InlineKeyboardButton('????????',  callback_data=f'pagenext#{incr_page}'),
            InlineKeyboardButton('????????',  callback_data=f'pageback#{decr_page}')
        ]
    keyboard.append(navigation_keyboard)
    keyboard.append(card_keyboard)
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup


@update_token
def start(elastickpath_access_token, client_id_secret, update: Update, context: CallbackContext) -> None:
    products = get_all_products(elastickpath_access_token.get('access_token'))
    update.message.reply_text(
        '???????????????????? ???????????????? ??????????',
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
    product_describtion = f'{product_name}\n{product_price_formatted} ????????????\n\n{product_text}'
    keyboard = [
        [
            InlineKeyboardButton('???????????????? 1 ?????????? ?? ??????????????', callback_data=f'{product_id}|card:1'),
            InlineKeyboardButton('???????????????? 2 ?????????? ?? ??????????????', callback_data=f'{product_id}|card:2')
            ],
        [InlineKeyboardButton('??????????????', callback_data='productcard')],
        [InlineKeyboardButton('??????????', callback_data='back')]
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
    update.callback_query.answer(text='?????????? ???????????????? ?? ??????????????')
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
        text='???????????????????? ???????????????? ??????????',
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
        products_describtion = f'{item_name}\n{item_price_per_item}?????? ???? ????\n{item_quantity}???? ?? ?????????????? ???? {item_total_price}??????\n\n'
        products_list.append(products_describtion)
        button = [InlineKeyboardButton(f'???????????? ???? ?????????????? {item_name}', callback_data=card_item_id)]
        keyboard.append(button)
    back_button = [InlineKeyboardButton('??????????', callback_data='back')]
    keyboard.append(back_button)
    pay_button = [InlineKeyboardButton('????????????????', callback_data='paybutton')]
    keyboard.append(pay_button)
    reply_markup = InlineKeyboardMarkup(keyboard)
    all_products = ''.join(product for product in products_list)
    card_message = f'{all_products}\n??????????:{card_total_price}??????'
    context.bot.send_message(
        chat_id=chat_id,
        text=card_message,
        reply_markup=reply_markup
    )
    return HANDLE_CART


@update_token
def remove_card_item(elastickpath_access_token, client_id_secret, update: Update, context: CallbackContext):
    chat_id = update.effective_message.chat_id
    query = update.callback_query
    product_id = query.data
    access_token = elastickpath_access_token.get('access_token')
    update.callback_query.answer(text='?????????? ???????????? ???? ??????????????')
    remove_cart_item(card_id=chat_id, product_id=product_id, access_token=access_token)
    handle_cart(elastickpath_access_token, client_id_secret, update, context)
    return HANDLE_CART


def handle_pay_request(redis_db, update: Update, context: CallbackContext):
    message_id = update.effective_message.message_id
    chat_id = update.effective_message.chat_id
    context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    message = '????????????, ???????????????? ?????? ?????? ?????????? ?????????????? ?????? ????????????????????'
    context.bot.send_message(
        chat_id=chat_id,
        text=message,
    )
    return WAITING_GEO


def handle_pay_request_geo(elastickpath_access_token, yandex_geo_api, update: Update, context: CallbackContext):
    chat_id = update.effective_message.chat_id
    user_geo = update.message.text
    user_geo_verified = fetch_coordinates(yandex_geo_api, user_geo)
    access_token = elastickpath_access_token.get('access_token')
    message = '????????????????, ???? ???? ???????????? ???????????????????? ???????? ????????????????????????????, ???????????????????? ???????????? ?????? ??????'
    if user_geo_verified:
        user_coordinates = user_geo_verified['GeoObject']['Point']['pos'].split(' ')
        nearest_restaurant = find_nearest_restaurant(user_coordinates, access_token)
        nearest_restaurant_distance = nearest_restaurant['distance']
        nearest_restaurant_address = nearest_restaurant['restuarant']
        if 0.5 >= nearest_restaurant_distance:
            message = f'?????????? ???????????????? ?????????? ???? ?????????? ???????????????? ????????????????????? \
                        ?????? ?????????????????? ?????????? ?? {nearest_restaurant_distance:1.2}???? ???? ??????! \
                        ?????? ???? ??????????: {nearest_restaurant_address}. ?? ?????????? ?????????????????? ????????????????!'
        elif 5 > nearest_restaurant_distance >= 0.5:
            message = f'?????????? ???????????????? ?????????? ???? ?????????? ????????????????? \
                        ?????? ?????????????????? ?? {nearest_restaurant_distance:1.2}???? ???? ??????! \
                        ?????? ???? ??????????: {nearest_restaurant_address}. \
                        ?? ?????????? ?????????????????? ???? 100??????'
        elif 20 >= nearest_restaurant_distance >= 5:
            message = f'?????????? ???????????????? ?????????? ???? ?????????? ????????????????? \
                        ?????? ?????????????????? ?? {nearest_restaurant_distance:1.2}???? ???? ??????! \
                        ?????? ???? ??????????: {nearest_restaurant_address}. \
                        ?? ?????????? ?????????????????? ???? 300??????'
        else:
            message = f'????????????????, ???? ???? ?????? ???????????? ?????????? ???? ????????????????.\
                        ?????????????????? ???????????????? ?????????????????? ???? ???????????????????? \
                        {nearest_restaurant_distance:1.2}????. ?????? \
                        ???? ?????????? {nearest_restaurant_address}'
    context.user_data.update(nearest_restaurant)
    keyboard = [
        [
            InlineKeyboardButton('??????????????????', callback_data='selfdelivery'),
            InlineKeyboardButton('????????????????', callback_data='delivery'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(
        chat_id=chat_id,
        text=message,
        reply_markup=reply_markup
    )
    return CLOSE_ORDER


def send_notification_to_courier(elastickpath_access_token, update: Update, context: CallbackContext):
    chat_id = update.effective_message.chat_id
    user_data = context.user_data
    user_coordinates = user_data['user_coordinates']
    access_token = elastickpath_access_token.get('access_token')
    cards = get_card(chat_id, access_token)
    card_items = get_card_items(chat_id, access_token)
    products_list = []
    total_quantity = 0
    card_total_price = cards.get('data').get('meta').get('display_price').get('with_tax').get('formatted').strip('RUB')
    for item in card_items.get('data'):
        item_name = item.get('name')
        item_quantity = item.get('quantity')
        total_quantity += int(item_quantity)
        products_list.append(item_name)
    all_products = ', '.join(product for product in products_list)
    message = f'{all_products}\n{total_quantity} ?????????? ?? ?????????????? ???? ?????????? {card_total_price}\n?? ????????????:{card_total_price}??????'
    lon, lat = user_coordinates
    context.bot.send_message(
        chat_id=chat_id,
        text=message
    )
    context.bot.send_location(
        chat_id=chat_id,
        latitude=lat,
        longitude=lon
    )


def notify_of_delay(context):
    message = '?????????????????? ????????????????! *?????????? ?????? ??????????????*\
               \n*??????????????????, ?????? ????????????, ???????? ?????????? ???? ????????????'
    context.bot.send_message(
        chat_id=context.job.context,
        text=message
    )


def handle_deliviry(elastickpath_access_token, job_queue, update: Update, context: CallbackContext):
    chat_id = update.effective_message.chat_id
    access_token = elastickpath_access_token.get('access_token')
    message = '?????? ???????????? ?????? ?? ????????. ?????????? ???????????????????? ???????????????? ??????????????'
    keyboard = [
        [
            InlineKeyboardButton('????????????', callback_data='payorder'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    send_notification_to_courier(elastickpath_access_token, update, context)
    context.bot.send_message(
        chat_id=chat_id,
        text=message,
        reply_markup=reply_markup
    )
    delay_hour = 60*60*60
    job_queue.run_once(notify_of_delay, delay_hour, context=chat_id)
    return CLOSE_ORDER


def handle_selfdeliviry(
    elastickpath_access_token,
    update: Update,
    context: CallbackContext
):
    chat_id = update.effective_message.chat_id
    user_data = context.user_data
    nearest_restaurant_coordinates = user_data['coordinates']
    lon, lat = nearest_restaurant_coordinates
    access_token = elastickpath_access_token.get('access_token')
    cards = get_card(chat_id, access_token)
    card_total_price = cards.get('data').get('meta').get('display_price').get('with_tax').get('formatted').strip('RUB')
    message = f'??????????! ???? ???????????????? ?????? ?????????? ???? ?????????????????? ????????????????. ???????????????? ???????????????? ??????????????, ?? ???????????? {card_total_price}??????'
    keyboard = [
        [
            InlineKeyboardButton('????????????', callback_data='payorder'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_location(
        chat_id=chat_id,
        latitude=lat,
        longitude=lon
    )
    context.bot.send_message(
        chat_id=chat_id,
        text=message,
        reply_markup=reply_markup
    )
    return CLOSE_ORDER


def start_without_shipping_callback(
    elastickpath_access_token,
    payment_token,
    update: Update,
    context: CallbackContext
) -> None:
    """Sends an invoice without shipping-payment."""
    chat_id = update.effective_message.chat_id
    access_token = elastickpath_access_token.get('access_token')
    cards = get_card(chat_id, access_token)
    card_total_price = cards.get('data').get('meta').get('display_price').get('with_tax').get('formatted').strip('RUB')
    title = "????????????"
    description = "?????????? ?????? ?????????????? ???????????? ?????????????? ???? ???????????? ?? ???????????? ???????????? ?? ???????????????? ??????????"
    payload = "Pizza-bot"
    currency = "RUB"
    price = int(sub(r'[^\d.]', '', card_total_price))
    prices = [LabeledPrice("PizzaBot", price * 100)]
    context.bot.send_invoice(
        chat_id, title, description, payload, payment_token, currency, prices
    )


def precheckout_callback(update: Update, context: CallbackContext) -> None:
    """Answers the PreQecheckoutQuery"""
    query = update.pre_checkout_query
    if query.invoice_payload != "Pizza-bot":
        query.answer(ok=False, error_message="Something went wrong...")
    else:
        query.answer(ok=True)


def successful_payment_callback(update: Update, context: CallbackContext) -> None:
    """Confirms the successful payment."""
    update.message.reply_text("Thank you for your payment!")
    end_conversation(update, context)


def handle_error(update: Update, context: CallbackContext):
    """Log Errors caused by Updates."""
    logger.warning(
        f'Update {update} caused error {context.error},\
        traceback {context.error.__traceback__}'
        )


def end_conversation(update: Update, context: CallbackContext):
    update.message.reply_text(
        '????????!'
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
    yandex_geo_api = os.getenv('YANDEX_GEO')
    payment_token = os.getenv('PAYMENT_PROVIDER_TOKEN')
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
    logger.info('Pizza store bot ??????????????')
    """Start the bot."""
    updater = Updater(token, persistence=persistence)
    job_queue = updater.job_queue
    dispatcher = updater.dispatcher
    job_queue.set_dispatcher(dispatcher=dispatcher)
    partial_start = partial(start, elastickpath_access_token, client_id_secret)
    partial_handle_menu = partial(handle_menu, elastickpath_access_token, client_id_secret)
    partial_handle_describtion = partial(handle_description, elastickpath_access_token, client_id_secret)
    partial_handle_cart = partial(handle_cart, elastickpath_access_token, client_id_secret)
    partial_handle_product_button = partial(handle_product_button, elastickpath_access_token, client_id_secret)
    partial_remove_card_item = partial(remove_card_item, elastickpath_access_token, client_id_secret)
    partial_handle_pay_request = partial(handle_pay_request, redis_base)
    partial_handle_pay_request_geo = partial(handle_pay_request_geo, elastickpath_access_token, yandex_geo_api)
    partial_handle_selfdeliviry = partial(handle_selfdeliviry, elastickpath_access_token)
    partial_handle_deliviry = partial(handle_deliviry, elastickpath_access_token, job_queue)
    partial_start_without_shipping_callback = partial(
        start_without_shipping_callback,
        elastickpath_access_token,
        payment_token
        )
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
                CallbackQueryHandler(partial_handle_cart, pattern="^(productcard)$"),
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
            WAITING_GEO: [
                MessageHandler(
                    Filters.text & ~Filters.command,
                    partial_handle_pay_request_geo
                    ),
            ],
            CLOSE_ORDER: [
                CallbackQueryHandler(partial_handle_selfdeliviry, pattern="^(selfdelivery)$"),
                CallbackQueryHandler(partial_handle_deliviry, pattern="^(delivery)$"),
                CallbackQueryHandler(
                    partial_start_without_shipping_callback,
                    pattern="^(payorder)$"
                    ),
            ]
        },
        fallbacks=[CommandHandler("end", end_conversation)],
        name="pizza_conversation",
        persistent=True
    )
    dispatcher.add_handler(conv_handler)
    dispatcher.add_error_handler(handle_error)
    dispatcher.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    dispatcher.add_handler(
        MessageHandler(Filters.successful_payment, successful_payment_callback)
    )
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
