import telebot
from telebot import types
import mysql.connector 
from mysql.connector import Error
from prettytable import PrettyTable, from_db_cursor

from KEYS import *

current_menu = "main_menu"

def escape_string(str):
    output = ""

    for char in str:
        if char == "<":
            output += "&lt;"
        elif char == ">":
            output += "&gt;"
        elif char == "&":
            output += "&amp;"
        else:
            output += char

    return output

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

def main_menu_handler(message):
    current_menu = "main_menu"
    if message.text == 'Створити таску':
        bot.send_message(message.chat.id,'Иди работай')
    elif message.text == 'Переглянути таски':
        show_tasks_as_buttons(message)
    elif message.text == 'Список членів СПФ':
        bot.send_message(message.chat.id, get_table_to_print(connection, "SELECT * FROM members", None), parse_mode='MarkdownV2')
    elif message.text == 'Звіт про помилку':
        bot.send_message(message.chat.id,'Ничё не работает')
    else:
        bot.send_message(message.chat.id,'Не зрозумів')

def show_tasks_as_buttons(message):
    markup = telebot.types.InlineKeyboardMarkup()
    description, response = query_db(connection, "SELECT * FROM tasks", None)
    i = 1
    for elem in response:
        markup.add(telebot.types.InlineKeyboardButton(text=elem[1], callback_data=elem[0]))
        i+=1
    bot.send_message(message.chat.id, text="Оберіть завдання", reply_markup=markup)

def show_task_by_id(call):
    markup = telebot.types.InlineKeyboardMarkup()
    description, response = query_db(connection, "SELECT * FROM tasks WHERE TaskID = %s", (call.data,))
    formatted = "<b>{}</b> - {}\n\n{}\n\n<i>{} - {}</i>\n\n<b>{}</b>\n\n<i>{}</i>\n\n".format(escape_string(response[0][1]), response[0][0], escape_string(response[0][2]), response[0][4], response[0][5], response[0][6], escape_string(response[0][3]))
    print(formatted)
    bot.send_message(call.from_user.id, formatted, parse_mode='HTML')
    
def text_message_handler(message):
    if message.chat.type == 'private':
        match current_menu:
            case "main_menu":
                main_menu_handler(message)
            case _:
                print("Invalid state {}".format(current_menu))
    

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    markup=make_main_menu()
    bot.send_message(message.chat.id,'Оберіть дію', reply_markup=markup)
  

@bot.message_handler(func=lambda message: True)
def reply_to_message(message):
    text_message_handler(message)

@bot.callback_query_handler(func=lambda call: True)    
def query_handler(call):
    match call.message.text:
        case "Оберіть завдання":
            show_task_by_id(call)


bot.infinity_polling()