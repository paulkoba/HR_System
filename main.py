import telebot
from telebot import types
import mysql.connector 
from mysql.connector import Error
from prettytable import PrettyTable, from_db_cursor

from KEYS import *

def create_connection(host_name, user_name, user_password, db_name):
    connection = None
    try:
        connection = mysql.connector.connect(
            host=host_name,
            user=user_name,
            passwd=user_password,
            database=db_name,
            auth_plugin='mysql_native_password',
            autocommit=True
        )
        print("Connection to MySQL DB '", db_name, "' successful")
    except Error as e:
        print(f"The error '{e}' occurred")

    return connection

connection = create_connection(IP, USERNAME, PASSWORD, "spf_management")

bot = telebot.TeleBot(TOKEN)

def query_db(connection, query, parameters):
    cursor = connection.cursor()

    try:
        if parameters is None:
            cursor.execute(query)
        else:
            cursor.execute(query, parameters)

        description = cursor.description
        return description, cursor.fetchall()

    except Error as e :
        print(f"The error '{e}' occurred")

def format_table_form_query_result(response, description, **kwargs):
    table = PrettyTable(**kwargs)
    table.align = "l"
    table.field_names = [col[0] for col in description]
    for row in response:
        table.add_row(row)
    return str(table)

def get_table_to_print(connection, query, parameters, **kwargs):
    description, response = query_db(connection, query, parameters)
    return '`' + format_table_form_query_result(response, description, **kwargs) + '`'

def make_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1=types.KeyboardButton("Створити таску")
    item2=types.KeyboardButton("Переглянути таски")
    item3=types.KeyboardButton("Список членів СПФ")
    item4=types.KeyboardButton("Звіт про помилку")
    markup.add(item1, item2)
    markup.add(item3, item4)
    return markup

def menu_handler(message):
    if message.text == 'Створити таску':
        bot.send_message(message.chat.id,'Иди работай')
    elif message.text == 'Переглянути таски':
        bot.send_message(message.chat.id,'Целая куча, иди работай')
    elif message.text == 'Список членів СПФ':
        bot.send_message(message.chat.id, get_table_to_print(connection, "SELECT * FROM members", None), parse_mode='MarkdownV2')
    elif message.text == 'Звіт про помилку':
        bot.send_message(message.chat.id,'Ничё не работает')
    else:
        bot.send_message(message.chat.id,'Не зрозумів')

def text_message_handler(message):
    if message.chat.type == 'private':
        menu_handler(message)
    

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    markup=make_main_menu()
    bot.send_message(message.chat.id,'Оберіть дію', reply_markup=markup)
  

@bot.message_handler(func=lambda message: True)
def reply_to_message(message):
    text_message_handler(message)

bot.infinity_polling()