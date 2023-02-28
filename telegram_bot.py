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
import db_search  # импортируем собственный модуль для поиск аи работы с базой данных
import stats  # импортируем собственный модуль для учета пользователей бота и прочей статистики
import requests

import uuid
from yookassa import Configuration, Payment, Webhook

# заморочки с вебхуками ***************************************************************************
WEBHOOK_HOST = config.whost  # IP-адрес сервера, на котором запущен бот
WEBHOOK_PORT = config.wport  # 443, 80, 88 или 8443 (порт должен быть открыт!)
WEBHOOK_LISTEN = config.wlisten  # На некоторых серверах придется указывать такой же IP, что и выше

WEBHOOK_SSL_CERT = config.app_dir + 'webhook_cert.pem'  # Путь к сертификату
WEBHOOK_SSL_PRIV = config.app_dir + 'webhook_pkey.pem'  # Путь к приватному ключу

WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/%s/" % (config.token)


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


# окончены заморочки с вебхуками ******************************************************************
bot = telebot.TeleBot(config.token)
subject = ''
delivery_address = ''

@bot.message_handler(func=lambda message: True, commands=['start'], content_types=['text', 'successful_payment'])
def start(message):
    if '/start' in message.text:
        # if message.text in ('/привет', '/Привет', 'Привет', 'привет'):
        bot.send_message(message.from_user.id, '*Товар или услуга?*\n'
                                               'Введи для поиска слово или фразу целиком или частично\n'
                                               '_Пример 1:_ Компьютер\n'
                                               '_Пример 2:_ Поставка комп',
                         parse_mode='MarkdownV2'
                         )
        bot.register_next_step_handler(message, get_subject)  # следующий шаг – функция get_subject
    else:
        bot.send_message(message.from_user.id, 'Напиши /start')

def get_subject(message):  # получаем от пользователя предмет закупки
    global subject
    subject = message.text
    bot.send_message(message.from_user.id, '*Регион оказания,поставки?*\n'
                                           'Введи для поиска слово или фразу целиком или частично\n'
                                           '*Для поиска по всем регионам введи* \nРФ / Россия / Все / Везде\n\n'
                                           '_Пример 1:_ Москва\n'
                                           '_Пример 2:_ Архангельская обл\n'
                                           '_Пример 3:_ Россия\n',
                     parse_mode='MarkdownV2'
                     )
    bot.register_next_step_handler(message, get_delivery_address)


def get_delivery_address(message):  # получаем от пользователя адрес поставки
    global delivery_address
    delivery_address = message.text
    bot.register_next_step_handler(message, post_query(message))
    stats.add_user(message)  # записать данные пользователя в базу для статистики
    # print(message)


# Функция клавиатуры для отправки запроса
def post_query(message):
    keyboard = types.InlineKeyboardMarkup()  # наша клавиатура
    key_yes = types.InlineKeyboardButton(text='\U00002705 Да', callback_data='yes')  # кнопка Да
    keyboard.add(key_yes)  # добавляем кнопку в клавиатуру
    key_no = types.InlineKeyboardButton(text='\U0001F6AB Нет', callback_data='no')  # кнопка Нет
    keyboard.add(key_no)
    question = 'Предмет закупки:' + subject + '\n Адрес выполнения:' + delivery_address + '\n \nВсе правильно?'  # потом сюда добавить остальные части вопроса
    bot.send_message(message.from_user.id, text=question, reply_markup=keyboard)
    #bot.register_next_step_handler(message, process_succ_payment) # раскомментить в случае работы через телегу напрямую


# функция отдачи контента после успешной оплаты если оплата через telegram
def process_succ_payment(message):
    print(message.content_type)
    if message.content_type == 'successful_payment':
        bot.send_message(message.chat.id, 'Счет оплачен!')  # появляется с задержкой почему то (((
        bot.send_message(message.chat.id, 'Вот результаты...')
        # формируем и отдаем оплаченный контент
        messages = db_search.search_db(subject, delivery_address)  # ищем в базе и обрабатываем результаты
        # print(messages)
        fil = db_search.file_prepare(messages)  # получаем файл ./big_res/your_results....xlsx
        try:
            uis_pdf = open(fil, 'rb')
            bot.send_document(message.chat.id, uis_pdf)  # отправляем файл с результатами
            uis_pdf.close()
        except:  # переписать обработчик на связь со службой техподдержки с номером транзакции отправка на почту
            bot.send_message(message.chat.id, 'Не могу отправить \U0001F622 \n' + config.for_new_search)
        bot.send_message(message.chat.id, config.for_new_search)
    # else:
    #     bot.send_message(message.chat.id, 'Сначала оплатите счет!')


#  функция потоковой отправки сообщений в ленту
def send_mes(call, messages, introduce):
    for i in range(len(messages)):
        bot_m = db_search.m_prepare(
            messages[i])  # внутри dbsearch функцией clean_query проверяем запрос на sql inject и удаляем слова-паразиты
        bot.send_message(call.message.chat.id, bot_m)
    # bot.send_message(call.message.chat.id, 'Это все что нашел... \n Для нового поиска напиши /привет')
    bot.send_message(call.message.chat.id, introduce)  # introduce -  текст сопроводительного сообщения


# функция клавиатуры для доната
def donate_keyboard(call, msg):
    #   # print('жопа')
    keyboard_dn = types.InlineKeyboardMarkup()
    key_url = types.InlineKeyboardButton(text='Помочь проекту\n(Ю money)', url=config.donate_url)
    keyboard_dn.add(key_url)
    bot.send_message(call.message.chat.id, text=msg, reply_markup=keyboard_dn)
    # return keyboard_dn


# функция клавиатуры для оплаты
def pay_keyboard(call, msg, price, url):
    keyboard_pay = types.InlineKeyboardMarkup()
    # keyboard_pay = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    txt = 'Оплатить ' + price + ' руб.'
    # key_url = types.InlineKeyboardButton(text=txt, url=url, callback_data='pay_api')
    key_url = types.InlineKeyboardButton(text=txt, url=url)  # еще в аргументы можно вставить callback_data =
    key_cancel = types.InlineKeyboardButton(text='Отмена', callback_data='no')  # еще в аргументы можно вставить callback_data =
    # key_url = types.KeyboardButton(txt)
    keyboard_pay.add(key_url)
    keyboard_pay.add(key_cancel)
    bot.send_message(call.message.chat.id, text=msg, reply_markup=keyboard_pay)
    # дальше сообщение что счет оплатчен и отдача результатов

# функция проверки статуса платежа
def get_payment_info(call,payment):
    bot.send_message(call.message.chat.id, 'Проверяем оплату (2-3 мин) ... ')
        # print('******************confirmation_url****************')
        # print(payment.confirmation.confirmation_url)
        # # https://yoomoney.ru/checkout/payments/v2/contract?orderId=2943d927-000f-5000-8000-175f8bbad0ab
        # # https://yoomoney.ru/payments/external/success?orderid=2943d927-000f-5000-8000-175f8bbad0ab
        # print('******************request****************')
        # payload = {'orderId':''+payment.id+''}
        # response = requests.get(payment.confirmation.confirmation_url, params=payload)  # переходим по ссылке подтверждения платежа
        # print(response.status_code) # код ответа от сервера - 200- OK
        # #time.sleep(100)
        #
    for i in range(25):
        time.sleep(5)  # получаем информацию о платеже с задержкой 5 сек - даем пользователю возможность оплатить всего 25*5=125 сек
        payment = Payment.find_one(payment.id)
        print('******************payment****************')
        print(payment.id, payment.status, payment.paid)
    return payment

# функция отдачи контента после успешной оплаты - переделана из оплаты в телеграм
def process_succ_payment_api(call, payment):
    # сначала необходимо проверить статус платежа
    payment_control = get_payment_info(call, payment)
    #print(Payment.find_one('2942fe04-000f-5000-a000-1e0eca57596b').id, Payment.find_one('2942fe04-000f-5000-a000-1e0eca57596b').status) # проверка на вшивость
    if payment_control.id == payment.id and payment_control.status == 'succeeded': # если платеж успешен
    #if response.id == payment.id and response.event == 'payment.succeeded': # если платеж успешен
        bot.send_message(call.message.chat.id, 'Счет оплачен!')  # появляется с задержкой почему то (((
        bot.send_message(call.message.chat.id, 'Вот результаты...')
        # формируем и отдаем оплаченный контент
        messages = db_search.search_db(subject, delivery_address)  # ищем в базе и обрабатываем результаты
        # print(messages)
        fil = db_search.file_prepare(messages,0)  # 0 - выводим все значения получаем файл ./big_res/your_results....xlsx
        try:
            uis_pdf = open(fil, 'rb')
            bot.send_document(call.message.chat.id, uis_pdf)  # отправляем файл с результатами
            # сюда добавить статистику по боевым примерам с записью в базу
            print('call message ********************************')
            print(call.message)
            user_id = call.message.chat.id  # получить id пользователя через сообщения
            print('user id  ****************************')
            print(user_id)
            file_size = os.stat(fil).st_size  # получить размер файла примера
            print('file_size ************************ ')
            print(file_size)
            file_type = 'pay'  # тип файла sample
            print('file type *********************** ')
            print(file_type)
            # file_date = call.message.date
            file_date = datetime.datetime.fromtimestamp(call.message.date).strftime(
                '%Y-%m-%d %H:%M:%S')  # дата время файла
            print('file_date *************************')
            print(file_date)
            search_text = call.message.text.replace('/n', ' ').replace('Все правильно?', '')
            print('search_text *******************')
            print(search_text)
            stats.add_stat_file(user_id, file_size, file_type, file_date,
                                search_text)  # записываем для файла примера в базу
            uis_pdf.close()
        except:  # переписать обработчик на связь со службой техподдержки с номером транзакции отправка на почту
            bot.send_message(call.message.chat.id, 'Не могу отправить \U0001F622 \n' + config.for_new_search)
        bot.send_message(call.message.chat.id, config.for_new_search)
    else: # во всех остальных случаях проверяем
        bot.send_message(call.message.chat.id, 'Счет не оплачен..')
        bot.send_message(call.message.chat.id, config.for_new_search)


# обработчик запроса на оплату при оплате из телеграмм
@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    print(pre_checkout_query.id)
    # сюда потом дописать размещение в таблице базы всех транзакций
    answer = bot.answer_pre_checkout_query(pre_checkout_query.id,
                                           ok=True)  # собственно отправка платежа считаем что он успешный
    # print(answer)

# Обработчик клавиатур взаимозависимых
@bot.callback_query_handler(func=lambda call: True)
def callback_worker(call):
    #print(call.data)
    if call.data == "yes":  # call.data это callback_data, которую мы указали при объявлении кнопки
        # bot.send_message(call.message.chat.id,
        #                  'Сейчас поищу...')  # вместо запомню фактическую выборку из базы подставить
        messages = db_search.search_db(subject, delivery_address)  # ищем в базе и обрабатываем результаты
        msg = 'Найдено ' + str(len(messages)) + ' результатов'

        # или сюда вставить механизм оплаты ######## пока заглушка #######################
        if len(messages) > 0:
            total_price = int(len(messages)) * int(config.one_result_price)

            pay_msg = 'Cтоимость 1 результата ' + str(config.one_result_price) + ' руб. \n' \
                                                                                 'К оплате ' + str(
                total_price) + ' руб.'
            # пример файла с результатами для пользователя
            bot.send_message(call.message.chat.id, 'Пример файла с результатами поиска...')
            fil_sample = db_search.file_prepare(messages,config.samples)  # ограничение для файла примера получаем файл ./big_res/your_results....xlsx
            try:
                uis_sample = open(fil_sample, 'rb')
                bot.send_document(call.message.chat.id, uis_sample)  # отправляем файл с результатами
                uis_sample.close()
                # сюда добавить статистику по файлу примера с записью в базу
                print('call message ********************************')
                print(call.message)
                user_id = call.message.chat.id  # получить id пользователя через сообщения
                print('user id  ****************************')
                print(user_id)
                file_size = os.stat(fil_sample).st_size # получить размер файла примера
                print('file_size ************************ ')
                print(file_size)
                file_type = 'sample'  # тип файла sample
                print('file type *********************** ')
                print(file_type)
                #file_date = call.message.date
                file_date = datetime.datetime.fromtimestamp(call.message.date).strftime('%Y-%m-%d %H:%M:%S')  # дата время файла
                print('file_date *************************')
                print(file_date)
                search_text = call.message.text.replace('/n',' ').replace('Все правильно?','')
                print('search_text *******************')
                print(search_text)
                stats.add_stat_file(user_id, file_size,file_type,file_date, search_text) # записываем для файла примера в базу
            except:  # переписать обработчик на связь со службой техподдержки с номером транзакции отправка на почту
                bot.send_message(call.message.chat.id, 'Не могу отправить \U0001F622 \n' + config.for_new_search)

            # а дальше клавиатура из 2 кнопок - оплатить разово или оформить подписку на сервис
            # при оформлении подписки использовать telegram passport
            # bot.send_message(call.message.chat.id, pay_msg)
            # pay_keyboard(call, pay_msg, str(total_price)) # потом вместо клавиатуры поставить сразу запрос способа оплаты
            if total_price > config.min_pay_summ:
                # дальше сюда вставить оплату и проверку оплаты пользователем
                # запрос на оплату картой
                Configuration.account_id = config.shopId
                Configuration.secret_key = config.y_api_secret
                payment = Payment.create({
                    "amount": {
                        "value": "" + str(total_price) + "",
                        "currency": "" + config.currency + ""
                    },
                    "confirmation": {
                        "type": "redirect",
                        #"return_url": "https://www.merchant-website.com/return_url"  # возвращаем чувака к бооту
                        "return_url": "https://t.me/Zakup_search_bot"  # возвращаем чувака к бооту
                    },
                    "capture": True,
                    "description": "" + config.description + ""
                }, uuid.uuid4())

                print('***************payment.json****************')
                print(payment.json())
                # ссылка для подтверждения
                confirmation_url = payment.confirmation.confirmation_url
                pay_keyboard(call, msg + '\n' + pay_msg, str(total_price),
                             confirmation_url)  # переходит по кнопке на форму оплаты по ссылке
                # как узнать что перешел по ссылке??????

                process_succ_payment_api(call, payment)  # при успешной оплате - отдача контента пользователю


                # старая оплата через телеграм

                # дальше обработчик успешного платежа
                # print(payment.paid)

                # старый механизм оплаты
                ######################################### старый механизм оплаты
                # prov_data = '{"receipt":{"email":"stilyn@yandex.ru","items":[{"description":"Оплата боту","quantity":"1.00","amount":{"value":"'+ str(total_price) +'","currency":"'+ config.currency +'"}},"vat_code":1]}'
                # invoice = bot.send_invoice(
                #     chat_id=call.message.chat.id,
                #     title=pay_msg,
                #     description=config.description,
                #     invoice_payload=config.invoice_payload,
                #     provider_token=config.provider_token,
                #     currency=config.currency,
                #     start_parameter='start_parameter',
                #     prices=[LabeledPrice(label=config.label, amount=(total_price * 100))],
                #     need_phone_number=None,
                #     need_email=True,
                #     # need_shipping_address=None,
                #     provider_data=json.dumps(prov_data)
                # )
                # print(invoice)
                ###################### конец механизма оплаты #############################

            else:  # раз оплата не проходит придется показывать бесплатно и потом совать донат
                try:
                    send_mes(call, messages, 'Вот результаты...')
                except:
                    bot.send_message(call.message.chat.id,
                                     'Не могу отправить \U0001F622 \n' + config.for_new_search)
                finally:
                    donate_keyboard(call, pay_msg + ' - можно задонатить \U0001F609')  # клавиатура для доната
                    bot.send_message(call.message.chat.id, config.for_new_search)
        else:
            bot.send_message(call.message.chat.id, 'Ничего не нашел... \U0001F622 \n' + config.for_new_search)
    elif call.data == "no":
        # bot.send_message(call.message.chat.id, 'Жаль \U0001F622 ' + config.for_new_search)
        bot.send_message(call.message.chat.id, config.for_new_search)

if __name__ == '__main__':  # идиома которая говорит скрипту что запуск идет отсюда до этого только функции и переменные
    # снова заморочки с вебхуками **************************************************************************************
    # Снимаем вебхук перед повторной установкой (избавляет от некоторых проблем)
    bot.remove_webhook()
    # Ставим заново вебхук
    bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH,
                    certificate=open(WEBHOOK_SSL_CERT, 'r'))
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


# НЕ РАБОТАЕТ ************** bot.polling(none_stop=True, interval=0)  # bot ждет сообщений пользователя
# А ВОТ ЭТО РАБОТАЕТ
# bot.infinity_polling(True)


# если бот вдруг закозлит то его надо в вечный цикл подробности здесь
# https://ru.stackoverflow.com/questions/711998/%D0%9D%D0%B5%D0%B4%D0%BE%D1%81%D1%82%D0%B0%D1%82%D0%BE%D0%BA-bot-polling

# ЭТО ТОЖЕ РАБОТАЕТ
# while True:
# try:
# bot.polling(none_stop=True, timeout=123)
# bot.infinity_polling(True)
# except Exception as e:
# print(e)  # или просто print(e) если у вас логгера нет,
# или
# import traceback; traceback.print_exc() # для печати полной инфы
# time.sleep(1)
