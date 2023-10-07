import telebot
import datetime

from telebot import types
from prettytable import PrettyTable
from enum import Enum
from KEYS import *

from database import query_db
from task import Task
from local_task_store import get_task_under_construction, get_task_under_construction_swap_buffer, set_task_under_construction, set_task_under_construction_buffer

role_id_to_role_name_cache = dict()

def get_member_username_from_id(id):
    _, response = query_db("SELECT * FROM users_id WHERE UserID = %s", (id,))

    if len(response) == 0:
        print("Couldn't retrieve username of user with ID: {}".format(id))
        return str(id)

    return '@' + response[0][1]

def update_id_username_relation(message):
    _, response = query_db("SELECT * FROM users_id WHERE UserID = %s", (message.from_user.id,))

    if response:
        query_db("UPDATE users_id SET Username = %s WHERE UserID = %s", (message.from_user.username, message.from_user.id))
    else:
        query_db("INSERT INTO users_id (UserID, Username) VALUES (%s, %s)", (message.from_user.id, message.from_user.username))

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
        query_db("INSERT INTO _states (ChatID, State) VALUES (%s, %s)", (chat_id, state.value))

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

    update_id_username_relation(message)

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
    global role_id_to_role_name_cache

    markup = telebot.types.InlineKeyboardMarkup()
    description, response = query_db("SELECT * FROM roles", None)
    i = 1
    role_id_to_role_name_cache = dict()
    for elem in response:
        markup.add(telebot.types.InlineKeyboardButton(text=elem[1], callback_data=elem[0]))
        role_id_to_role_name_cache[elem[0]] = elem[1]
        i+=1
    bot.send_message(message.chat.id, text="👇", reply_markup=markup)

def show_task_by_id(call):
    markup = telebot.types.InlineKeyboardMarkup()
    description, response = query_db("SELECT * FROM tasks WHERE TaskID = %s", (call.data,))
    formatted = "№{}\n<b>{}</b>\n\n{}\n\nСтворено: <i>{}</i>\nДедлайн: <i>{}</i>\n\nВартість: <b>{}</b>\n\nАвтор: <i>{}</i>\n\n".format(response[0][0], escape_string(response[0][1]), escape_string(response[0][2]), response[0][4], response[0][5], response[0][6], get_member_username_from_id(response[0][3]))
    bot.send_message(call.from_user.id, formatted, parse_mode='HTML')
    
    values = response[0][7].split(' ')
    index = 0
    while index < len(values) - 1:
        bot.forward_message(call.from_user.id, values[index], values[index + 1])
        index += 2

def preview_task(task, message):
    markup = telebot.types.InlineKeyboardMarkup()
    formatted = "<b>{}</b>\n\n{}\n\nДедлайн: <i>{}</i>\n\nВартість: <b>{}</b>\n\nАвтор: <i>{}</i>\n\n".format(task.name, task.description, task.due_date, task.estimate, get_member_username_from_id(message.from_user.id))
    bot.send_message(message.chat.id, formatted, parse_mode='HTML')
    
    for el in task.attachments:
        bot.forward_message(message.chat.id, el[0], el[1])
    
    
def add_role_to_task(call):
    buffer = get_task_under_construction_swap_buffer(call.from_user.id)
    try:
        if int(call.data) not in buffer.roles:
            bot.send_message(call.from_user.id, text="Додано роль: {}".format(role_id_to_role_name_cache[int(call.data)]))
        else:
            bot.send_message(call.from_user.id, text="Дана роль вже прикріплена до завдання.")
    except:
        print("Couln't find role name matching role ID {}".format(call.data))
    buffer.roles.append(int(call.data))
    set_task_under_construction_buffer(call.from_user.id, buffer)

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
    task.author = message.from_user.id
    query_db("INSERT INTO spf_management.tasks (TaskName, TaskDescription, AuthorID, CreationDate, DueDate, Estimate, Attachment) VALUES (%s, %s, %s, %s, %s, %s, %s)", (task.name, task.description, task.author, task.creation_date, task.due_date, task.estimate, ' '.join([attachment[0] + " " + attachment[1] for attachment in task.attachments])))

def render_optionals_menu(message):
    set_state(message.chat.id, States.CREATE_TASK_OPTIONALS)
    bot.send_message(message.chat.id,'Заповніть опціональні поля та підтвердіть створення завдання', reply_markup=create_edit_task_menu())

def create_task(current_menu, message):
    match current_menu:
        case States.MAIN_MENU:
            set_task_under_construction(message.chat.id, Task())
            set_task_under_construction_buffer(message.chat.id, Task())

            set_state(message.chat.id, States.CREATE_TASK_NAME)
            bot.send_message(message.chat.id,'Введіть назву завдання', reply_markup=create_cancel_menu())
        case States.CREATE_TASK_NAME:
            if message.text == "Назад":
                execute_cancel_menu(message)
                return
            buffer = get_task_under_construction(message.chat.id)
            buffer.name = message.text
            set_task_under_construction(message.chat.id, buffer)
            set_state(message.chat.id, States.CREATE_TASK_DESCRIPTION)
            bot.send_message(message.chat.id,'Введіть опис завдання', reply_markup=create_cancel_menu())
        case States.CREATE_TASK_DESCRIPTION:
            if message.text == "Назад":
                execute_cancel_menu(message)
                return

            buffer = get_task_under_construction(message.chat.id)
            buffer.description = message.text
            set_task_under_construction(message.chat.id, buffer)

            set_state(message.chat.id, States.CREATE_TASK_OPTIONALS)
            bot.send_message(message.chat.id,'Заповніть опціональні поля та підтвердіть створення завдання', reply_markup=create_edit_task_menu())
        case States.CREATE_TASK_CHANGE_NAME:
            if message.text == "Назад":
                render_optionals_menu(message)
                return

            buffer = get_task_under_construction(message.chat.id)
            buffer.name = message.text
            set_task_under_construction(message.chat.id, buffer)
            render_optionals_menu(message)
        
        case States.CREATE_TASK_CHANGE_DESCRIPTION:
            if message.text == "Назад":
                render_optionals_menu(message)
                return
            buffer = get_task_under_construction(message.chat.id)
            buffer.description = message.text
            set_task_under_construction(message.chat.id, buffer)
            render_optionals_menu(message)

        case States.CREATE_TASK_CHANGE_ESTIMATE:
            if message.text == "Назад":
                render_optionals_menu(message)
                return
            buffer = get_task_under_construction(message.chat.id)

            try:
                float(message.text)
                buffer.estimate = message.text
                
                set_task_under_construction(message.chat.id, buffer)
                render_optionals_menu(message)
            except ValueError:
                bot.send_message(message.chat.id, "Будь-ласка введіть число.", reply_markup=create_cancel_menu())

        case States.CREATE_TASK_CHANGE_ROLES:
            if message.text == "Назад":
                render_optionals_menu(message)
                return

            if message.text == "OK":
                buffer = get_task_under_construction(message.chat.id)
                swap_buffer = get_task_under_construction_swap_buffer(message.chat.id)
                buffer.roles = swap_buffer.roles
                swap_buffer.roles = []
                set_task_under_construction_buffer(message.chat.id, swap_buffer)
                set_task_under_construction(message.chat.id, buffer)

                render_optionals_menu(message)
                return

            render_optionals_menu(message)

        case States.CREATE_TASK_CHANGE_ATTACHMENT:
            if message.text == "Назад":
                render_optionals_menu(message)
                return

            if message.text == "OK":
                buffer = get_task_under_construction(message.chat.id)
                swap_buffer = get_task_under_construction_swap_buffer(message.chat.id)
                buffer.attachments = swap_buffer.attachments
                swap_buffer.attachments = []
                set_task_under_construction_buffer(message.chat.id, swap_buffer)
                set_task_under_construction(message.chat.id, buffer)

                render_optionals_menu(message)
                return

            buffer = get_task_under_construction_swap_buffer(message.chat.id)
            buffer.attachments.append([str(message.chat.id), str(message.message_id)])
            set_task_under_construction_buffer(message.chat.id, buffer)

        case States.CREATE_TASK_OPTIONALS:
            # TODO: Fix hardcoded message contents
            if message.text == "Назва завдання":
                set_state(message.chat.id, States.CREATE_TASK_CHANGE_NAME)
                bot.send_message(message.chat.id, 'Введіть назву завдання', reply_markup=create_cancel_menu())
                return

            if message.text == "Опис завдання":
                set_state(message.chat.id, States.CREATE_TASK_CHANGE_DESCRIPTION)
                bot.send_message(message.chat.id, 'Введіть опис завдання', reply_markup=create_cancel_menu())
                return

            if message.text == "Estimate":
                set_state(message.chat.id, States.CREATE_TASK_CHANGE_ESTIMATE)
                bot.send_message(message.chat.id, 'Введіть estimate:', reply_markup=create_cancel_menu())
                return

            if message.text == "Ролі виконавців":
                set_state(message.chat.id, States.CREATE_TASK_CHANGE_ROLES)
                bot.send_message(message.chat.id, 'Оберіть ролі виконавців', reply_markup=create_cancel_approve_menu())
                show_roles_as_buttons(message)
                return

            if message.text == "Прикріплення":
                set_state(message.chat.id, States.CREATE_TASK_CHANGE_ATTACHMENT)
                bot.send_message(message.chat.id, 'Відправте прикріплення:', reply_markup=create_cancel_approve_menu())
                return

            if message.text == "Назад":
                execute_cancel_menu(message)
                return

            if message.text == "Preview":
                preview_task(get_task_under_construction(message.chat.id), message)
                return

            if message.text == "Створити":
                execute_create_task(get_task_under_construction(message.chat.id), message)
                set_state(message.chat.id, States.MAIN_MENU)
                render_main_menu(message)
                set_task_under_construction(message.chat.id, Task())
                set_task_under_construction_buffer(message.chat.id, Task())
                
                return

            render_optionals_menu(message)
    

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    set_state(message.chat.id, States.MAIN_MENU)

    render_main_menu(message)
  

@bot.message_handler(content_types=['document', 'photo', 'audio', 'video', 'voice'])
def document_handler(message):
    print("Received document: {}".format(message))
    state = get_state(message.chat.id)
    if state == States.CREATE_TASK_CHANGE_ATTACHMENT:
        swap_buffer = get_task_under_construction_swap_buffer(message.chat.id)
        swap_buffer.attachments.append([str(message.chat.id), str(message.message_id)])
        set_task_under_construction_buffer(message.chat.id, swap_buffer)

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
        case "👇": # TODO: ???
            add_role_to_task(call)

bot.infinity_polling()