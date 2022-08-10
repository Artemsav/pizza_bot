# Бот Pizza bot

Это MVP чат-бота #fixme



## Запуск

Python3 должен быть уже установлен. #fixme

* Скачайте код
* Установите зависимости  
```pip install -r requirements.txt```
* Запустите бот командой  
```python3 manage.py bot```
* Для доступа к админке  
```python3 manage.py createsuperuser```
```python3 manage.py migrate```
```python3 manage.py runserver```
На команду `/start` должен отреагировать, значит проект развернулся, все ок.

## Переменные окружения

Для корректной работы кода необходимо указать переменные окружения. Для этого создайте файл `.env` рядом с `manage.py` и запишите туда следующие обязательные переменые: #fixme

* `TELEGRAM_API_KEY` - Токен ключ бота в Телеграм;
* `DJANGO_SECRET_KEY` - Секретный ключ Django;
* `TG_USER_ID` - чат id для логов в телеграмме
* `TG_TOKEN_LOGGING` - Токен ключ бота в Телеграм для логов;
* `REDIS_HOST` 
* `REDIS_PORT`
* `REDIS_PASS` - данные для доступа к БЗ Redis. Брать в личном кабинете на [сайте](https://redis.io/)
* `DEBUG=TRUE` - включить, выключить режим DEBUG. Подробности в доке [джанго](https://docs.djangoproject.com/en/4.0/ref/settings/)

