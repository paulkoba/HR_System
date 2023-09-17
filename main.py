import telebot
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

def QueryDB(connection, query, parameters):
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

def FormatTableFromQueryResult(response, description, **kwargs):
    table = PrettyTable(**kwargs)
    table.align = "l"
    table.field_names = [col[0] for col in description]
    for row in response:
        table.add_row(row)
    return str(table)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
	bot.reply_to(message, "Howdy, how are you doing?")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    description, response = QueryDB(connection, "SELECT * FROM members", None)
    formatted_table = FormatTableFromQueryResult(response, description)
    bot.reply_to(message, '`' + formatted_table + '`', parse_mode='MarkdownV2')

bot.infinity_polling()