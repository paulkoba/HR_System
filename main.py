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

def CreateQuery(connection, query, parameter=None, is_str=True):
    cursor = connection.cursor()
    mytable = PrettyTable()
    try:
        if parameter is None:
            cursor.execute(query)
            
        else:
            cursor.execute(query, parameter)    
            if not is_str:          
                x = cursor.fetchall()
                if x == []:
                    return None
                if x[0][0] == 0 or x[0][0] == 1:
                    return x[0][0]

        
        if is_str:            
            mytable = from_db_cursor(cursor)
            if mytable == None:
                return None
            mytable.align='l'
            return str(mytable)
        else:
            if parameter is None:
                res = cursor.fetchall()
                res = [ i[0] for i in res ]
                return res
            else:
                x = [ i[0] for i in x ]
                return x

        
    except Error as e :
        print(f"The error '{e}' occurred")


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
	bot.reply_to(message, "Howdy, how are you doing?")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
	bot.reply_to(message, '`' + CreateQuery(connection, "SELECT * FROM members", None, True) + '`', parse_mode='MarkdownV2')

bot.infinity_polling()