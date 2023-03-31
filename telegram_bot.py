#!/usr/bin/env python3
# coding: utf-8
# -*- coding: utf-8 -*-

"""
Это бот в телеграм для общения с потребителями сервиса
Запуск из терминала  - python3 montp/montp_app/telegram_bot.py
TOKEN=626772406:AAE4f1yavUhqa6IWlZAxv4AhOm5W8boWwts
КАНАЛ - туда для статистики можно пиндюрить пользовательские запросы
CHAT_ID=-1001289100380 #- это чат ID канала
"""
import json
import time
import datetime
import os
import cherrypy
import telebot
from telebot import types
from telebot.types import LabeledPrice
import config  # импортируем собственный модуль конфигурации

# import db_search  # импортируем собственный модуль для поиск аи работы с базой данных
# import stats  # импортируем собственный модуль для учета пользователей бота и прочей статистики
# import requests
#
# import uuid

# заморочки с вебхуками ***************************************************************************
WEBHOOK_HOST = config.whost  # IP-адрес сервера, на котором запущен бот
WEBHOOK_PORT = config.wport  # 443, 80, 88 или 8443 (порт должен быть открыт!)
WEBHOOK_LISTEN = config.wlisten  # На некоторых серверах придется указывать такой же IP, что и выше

WEBHOOK_SSL_CERT = config.app_dir + 'webhook_cert.pem'  # Путь к сертификату
WEBHOOK_SSL_PRIV = config.app_dir + 'webhook_pkey.pem'  # Путь к приватному ключу

WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/%s/" % (config.token)

bot = telebot.TeleBot(config.token)


@bot.message_handler(commands=['start'])
def command_start(message):
    bot.send_message(message.chat.id, '*Привет*\n'
                                      'Это тетовая мессага бота2',
                     parse_mode='MarkdownV2')


# Наш вебхук-сервер
class WebhookServer(object):
    @cherrypy.expose
    def index(self):
        if 'content-length' in cherrypy.request.headers and \
                'content-type' in cherrypy.request.headers and \
                cherrypy.request.headers['content-type'] == 'application/json':
            length = int(cherrypy.request.headers['content-length'])
            json_string = cherrypy.request.body.read(length).decode("utf-8")
            update = telebot.types.Update.de_json(json_string)
            # Эта функция обеспечивает проверку входящего сообщения
            bot.process_new_updates([update])
            # print(update)
            return ''
        else:
            raise cherrypy.HTTPError(403)


if __name__ == '__main__':  # идиома которая говорит скрипту что запуск идет отсюда до этого только функции и переменные
    # снова заморочки с вебхуками **************************************************************************************
    # Снимаем вебхук перед повторной установкой (избавляет от некоторых проблем)
    bot.remove_webhook()
    # Ставим заново вебхук
    bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH, certificate=open(WEBHOOK_SSL_CERT, 'r'))
    # bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH)
    # Указываем настройки сервера CherryPy
    cherrypy.config.update({
        'server.socket_host': WEBHOOK_LISTEN,
        'server.socket_port': WEBHOOK_PORT,
        'server.ssl_module': 'builtin',
        'server.ssl_certificate': WEBHOOK_SSL_CERT,
        'server.ssl_private_key': WEBHOOK_SSL_PRIV
    })
    # Собственно, запуск!
    cherrypy.quickstart(WebhookServer(), WEBHOOK_URL_PATH, {'/': {}})
    # конец заморочек с вебхуками *************************************************************************************
