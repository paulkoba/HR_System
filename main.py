import telebot
import datetime
from database import query_db
from telebot import types
from prettytable import PrettyTable
from enum import Enum

from KEYS import *

class Task:
    name = ""
    description = ""
    roles = []
    assignees = []
    due_date = "1970-01-01 00:00:00"
    creation_date = "1970-01-01 00:00:00"
    attachments = []
    estimate = 0
    author = 0

task_under_construction = Task()
task_under_construction_swap_buffer = Task()

class States(Enum):
    MAIN_MENU = 1
    CREATE_TASK_NAME = 2
    CREATE_TASK_DESCRIPTION = 3
    CREATE_TASK_OPTIONALS = 4
    CREATE_TASK_CHANGE_NAME = 5
    CREATE_TASK_CHANGE_DESCRIPTION = 6
    CREATE_TASK_CHANGE_ROLES = 7
    CREATE_TASK_CHANGE_ASSIGNEES = 8
    CREATE_TASK_CHANGE_ESTIMATE = 9
    CREATE_TASK_CHANGE_ATTACHMENT = 10

bot = telebot.TeleBot(TOKEN)

def get_state(chat_id):
    _, response = query_db("SELECT State FROM _states WHERE ChatID = %s", (chat_id,))

    if len(response) == 0:
        set_state(chat_id, States.MAIN_MENU)
        _, response = query_db("SELECT State FROM _states WHERE ChatID = %s", (chat_id,))

    print("Received state {}".format(response[0][0]))
    return States(response[0][0])

def set_state(chat_id, state):
    print("Setting state to {}".format(state))
    _, response = query_db("SELECT * FROM _states WHERE ChatID = %s", (chat_id,))

    if response:
        query_db("UPDATE _states SET State = %s WHERE ChatID = %s", (state.value, chat_id))
    else:
        query_db("INSERT INTO _states (ChatID, State) VALUES (%s, %s)", (chat_id, state.value));

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

def format_table_form_query_result(response, description, **kwargs):
    table = PrettyTable(**kwargs)
    table.align = "l"
    table.field_names = [col[0] for col in description]
    for row in response:
        table.add_row(row)
    return str(table)

def get_table_to_print(query, parameters, **kwargs):
    description, response = query_db(query, parameters)
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
    set_state(message.chat.id, States.MAIN_MENU)
    if message.text == 'Створити таску':
        create_task(get_state(message.chat.id), message)
    elif message.text == 'Переглянути таски':
        show_tasks_as_buttons(message)
    elif message.text == 'Список членів СПФ':
        bot.send_message(message.chat.id, get_table_to_print("SELECT * FROM members", None), parse_mode='MarkdownV2')
    elif message.text == 'Звіт про помилку':
        bot.send_message(message.chat.id,'Ничё не работает')
    else:
        print("Received message \"{}\" in main_menu_handler".format(message.text))

def render_main_menu(message):
    markup=make_main_menu()
    bot.send_message(message.chat.id,'Оберіть дію', reply_markup=markup)

def show_tasks_as_buttons(message):
    markup = telebot.types.InlineKeyboardMarkup()
    description, response = query_db("SELECT * FROM tasks", None)
    i = 1
    for elem in response:
        markup.add(telebot.types.InlineKeyboardButton(text=elem[1], callback_data=elem[0]))
        i+=1
    bot.send_message(message.chat.id, text="Оберіть завдання", reply_markup=markup)

def show_roles_as_buttons(message):
    markup = telebot.types.InlineKeyboardMarkup()
    description, response = query_db("SELECT * FROM roles", None)
    i = 1
    for elem in response:
        markup.add(telebot.types.InlineKeyboardButton(text=elem[1], callback_data=elem[0]))
        i+=1
    bot.send_message(message.chat.id, text="Оберіть ролі", reply_markup=markup)     

def show_task_by_id(call):
    markup = telebot.types.InlineKeyboardMarkup()
    description, response = query_db("SELECT * FROM tasks WHERE TaskID = %s", (call.data,))
    formatted = "<b>{}</b> - {}\n\n{}\n\n<i>{} - {}</i>\n\n<b>{}</b>\n\n<i>{}</i>\n\n".format(escape_string(response[0][1]), response[0][0], escape_string(response[0][2]), response[0][4], response[0][5], response[0][6], response[0][3])
    bot.send_message(call.from_user.id, formatted, parse_mode='HTML')
    
def add_role_to_task(call):
    task_under_construction_swap_buffer.roles.append(int(call.data))
    bot.send_message(call.from_user.id, text="Додано роль: {}".format(call.data))

def text_message_handler(message):
    current_menu = get_state(message.chat.id)

    if message.chat.type == 'private':
        match current_menu:
            case States.MAIN_MENU:
                main_menu_handler(message)
            case States.CREATE_TASK_NAME:
                create_task(current_menu, message)
            case States.CREATE_TASK_DESCRIPTION:
                create_task(current_menu, message)
            case States.CREATE_TASK_OPTIONALS:
                create_task(current_menu, message)
            case States.CREATE_TASK_CHANGE_NAME:
                create_task(current_menu, message)
            case States.CREATE_TASK_CHANGE_DESCRIPTION:
                create_task(current_menu, message)
            case States.CREATE_TASK_CHANGE_ROLES:
                create_task(current_menu, message)
            case States.CREATE_TASK_CHANGE_ASSIGNEES:
                create_task(current_menu, message)
            case States.CREATE_TASK_CHANGE_ESTIMATE:
                create_task(current_menu, message)
            case States.CREATE_TASK_CHANGE_ATTACHMENT:
                create_task(current_menu, message)                                                                                         
            case _:
                print("Invalid state {}".format(current_menu))

def execute_cancel_menu(message):
    set_state(message.chat.id, States.MAIN_MENU)
    render_main_menu(message)

def create_cancel_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1=types.KeyboardButton("Назад")
    markup.add(item1)
    return markup

def create_cancel_approve_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1=types.KeyboardButton("Назад")
    item2=types.KeyboardButton("OK")
    markup.add(item1, item2)
    return markup

def create_edit_task_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    item1=types.KeyboardButton("Назва завдання")
    item2=types.KeyboardButton("Опис завдання")
    item3=types.KeyboardButton("Ролі виконавців")
    item4=types.KeyboardButton("Додати виконавців")
    item5=types.KeyboardButton("Дедлайн")
    item6=types.KeyboardButton("Прикріплення")
    item7=types.KeyboardButton("Estimate")
    item8=types.KeyboardButton("Назад")
    item9=types.KeyboardButton("Preview")
    item10=types.KeyboardButton("Створити")

    markup.add(item1, item2)
    markup.add(item3, item4)
    markup.add(item5, item6, item7)
    markup.add(item8, item9, item10)

    return markup

def execute_create_task(task, message):
    task.creation_date = datetime.datetime.now()
    query_db("INSERT INTO spf_management.tasks (TaskName, TaskDescription, AuthorID, CreationDate, DueDate, Estimate, Attachment) VALUES (%s, %s, %s, %s, %s, %s, %s)", (task.name, task.description, task.author, task.creation_date, task.due_date, task.estimate, ' '.join(task.attachments)))

def render_optionals_menu(message):
    set_state(message.chat.id, States.CREATE_TASK_OPTIONALS)
    bot.send_message(message.chat.id,'Заповніть опціональні поля та підтвердіть створення завдання', reply_markup=create_edit_task_menu())

def create_task(current_menu, message):
    global task_under_construction
    global task_under_construction_swap_buffer

    match current_menu:
        case States.MAIN_MENU:
            task_under_construction = Task()
            task_under_construction_swap_buffer = Task()
            set_state(message.chat.id, States.CREATE_TASK_NAME)
            bot.send_message(message.chat.id,'Введіть назву завдання', reply_markup=create_cancel_menu())
        case States.CREATE_TASK_NAME:
            if message.text == "Назад":
                execute_cancel_menu(message)
                return
            task_under_construction.name = message.text
            set_state(message.chat.id, States.CREATE_TASK_DESCRIPTION)
            bot.send_message(message.chat.id,'Введіть опис завдання', reply_markup=create_cancel_menu())
        case States.CREATE_TASK_DESCRIPTION:
            if message.text == "Назад":
                execute_cancel_menu(message)
                return

            task_under_construction.description = message.text

            set_state(message.chat.id, States.CREATE_TASK_OPTIONALS)
            bot.send_message(message.chat.id,'Заповніть опціональні поля та підтвердіть створення завдання', reply_markup=create_edit_task_menu())
        case States.CREATE_TASK_CHANGE_NAME:
            if message.text == "Назад":
                render_optionals_menu(message)
                return
            task_under_construction.name = message.text
            render_optionals_menu(message)
        
        case States.CREATE_TASK_CHANGE_DESCRIPTION:
            if message.text == "Назад":
                render_optionals_menu(message)
                return
            task_under_construction.description = message.text
            render_optionals_menu(message)

        case States.CREATE_TASK_CHANGE_ESTIMATE:
            if message.text == "Назад":
                render_optionals_menu(message)
                return
            task_under_construction.estimate = message.text
            render_optionals_menu(message)

        case States.CREATE_TASK_CHANGE_ROLES:
            if message.text == "Назад":
                render_optionals_menu(message)
                return

            if message.text == "OK":
                task_under_construction.roles = task_under_construction_swap_buffer.roles
                task_under_construction_swap_buffer.roles = []
                render_optionals_menu(message)
                return

            render_optionals_menu(message)

        case States.CREATE_TASK_OPTIONALS:
            # TODO: Fix hardcoded message contents
            if message.text == "Назва завдання":
                set_state(message.chat.id, States.CREATE_TASK_CHANGE_NAME)
                bot.send_message(message.chat.id,'Введіть назву завдання', reply_markup=create_cancel_menu())
                return

            if message.text == "Опис завдання":
                set_state(message.chat.id, States.CREATE_TASK_CHANGE_DESCRIPTION)
                bot.send_message(message.chat.id,'Введіть опис завдання', reply_markup=create_cancel_menu())
                return

            if message.text == "Estimate":
                set_state(message.chat.id, States.CREATE_TASK_CHANGE_ESTIMATE)
                bot.send_message(message.chat.id,'Введіть estimate:', reply_markup=create_cancel_menu())
                return

            if message.text == "Ролі виконавців":
                set_state(message.chat.id, States.CREATE_TASK_CHANGE_ROLES)
                bot.send_message(message.chat.id,'Оберіть ролі виконавців', reply_markup=create_cancel_approve_menu())
                show_roles_as_buttons(message)
                return

            if message.text == "Назад":
                execute_cancel_menu(message)
                return

            if message.text == "Створити":
                execute_create_task(task_under_construction, message)
                set_state(message.chat.id, States.MAIN_MENU)
                render_main_menu(message)
                return

            render_optionals_menu(message)
    

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    set_state(message.chat.id, States.MAIN_MENU)

    render_main_menu(message)
  

@bot.message_handler(func=lambda message: True)
def reply_to_message(message):
    print("Reply to message: {}".format(message.text))
    text_message_handler(message)

@bot.callback_query_handler(func=lambda call: True)
def query_handler(call):
    print("Callback query handler: {}".format(call.data))

    match call.message.text:
        case "Оберіть завдання":
            show_task_by_id(call)
        case "Оберіть ролі":
            add_role_to_task(call)

bot.infinity_polling()