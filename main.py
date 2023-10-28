import telebot
import datetime
import localization
import anonymous_voting

from telebot import types
from prettytable import PrettyTable
from enum import Enum
from KEYS import *

from database import query_db
from task import Task
from local_task_store import get_task_under_construction, get_task_under_construction_swap_buffer, \
    set_task_under_construction, set_task_under_construction_swap_buffer

role_id_to_role_name_cache = dict()


def get_member_username_from_id(id):
    _, response = query_db("SELECT * FROM users_id WHERE UserID = %s", (id,))

    if len(response) == 0:
        print("Couldn't retrieve username of user with ID: {}".format(id))
        return str(id)

    return response[0][1]


def update_id_username_relation(message):
    _, response = query_db("SELECT * FROM users_id WHERE UserID = %s", (message.from_user.id,))

    if response:
        query_db("UPDATE users_id SET Username = @%s WHERE UserID = %s",
                 (message.from_user.username, message.from_user.id))
    else:
        query_db("INSERT INTO users_id (UserID, Username) VALUES (%s, @%s)",
                 (message.from_user.id, message.from_user.username))


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
    CREATE_TASK_CHANGE_DUE_DATE = 11
    DEPARTMENT_SELECTION_MENU = 12
    CREATE_VOTING = 13


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
    item1 = types.KeyboardButton(localization.CreateTask)
    item2 = types.KeyboardButton(localization.ViewTasks)
    item3 = types.KeyboardButton(localization.ListOfMembersSPF)
    item4 = types.KeyboardButton(localization.ReportError)
    item5 = types.KeyboardButton(localization.AnonymousVoting)
    markup.add(item1, item2)
    markup.add(item3, item4)
    markup.add(item5)
    return markup


def main_menu_handler(message):
    set_state(message.chat.id, States.MAIN_MENU)
    if message.text == localization.CreateTask:
        create_task(get_state(message.chat.id), message)
    elif message.text == localization.ViewTasks:
        show_tasks_as_buttons(message)
    elif message.text == localization.ListOfMembersSPF:
        set_state(message.chat.id, States.DEPARTMENT_SELECTION_MENU)
        bot.send_message(message.chat.id, localization.DepartmentSelectionMenuMessage,
                         reply_markup=create_department_selection_menu())
    elif message.text == localization.ReportError:
        bot.send_message(message.chat.id, localization.NothingWorks)
    elif message.text == localization.AnonymousVoting:
        set_state(message.chat.id, States.CREATE_VOTING)
        create_anonymous_voting(message)
    else:
        print("Received message \"{}\" in main_menu_handler".format(message.text))


def department_selection_menu_handler(message):
    table = ""
    if message.text == localization.InfoDepartment:
        table += "info_department"
    elif message.text == localization.CulturalDepartment:
        table = "cultural_department"
    elif message.text == localization.ScienceDepartment:
        table = "science_department"
    elif message.text == localization.ChytalkaDepartment:
        table = "chytalka_department"
    elif message.text == localization.AllDepartments:
        table = "members"
    elif message.text == localization.Back:
        execute_cancel_menu(message)
        return
    else:
        print("Received message \"{}\" in department_selection_menu_handler".format(message.text))
    description, response = query_db(f"SELECT COUNT(*) FROM {table}", None)
    participants_table_row_count = int(response[0][0])
    page_size = 35
    page = 1
    offset = (page - 1) * page_size
    while offset < participants_table_row_count:
        bot.send_message(message.chat.id,
                         get_table_to_print(f"SELECT * FROM {table} LIMIT {page_size} OFFSET {offset}", None),
                         parse_mode='MarkdownV2')
        page += 1
        offset = (page - 1) * page_size


def render_main_menu(message):
    markup = make_main_menu()

    update_id_username_relation(message)

    bot.send_message(message.chat.id, localization.ChooseAction, reply_markup=markup)


def show_tasks_as_buttons(message):
    markup = telebot.types.InlineKeyboardMarkup()
    description, response = query_db("SELECT * FROM tasks", None)
    i = 1
    for elem in response:
        markup.add(telebot.types.InlineKeyboardButton(text=elem[1], callback_data=elem[0]))
        i += 1
    bot.send_message(message.chat.id, text=localization.ChooseTask, reply_markup=markup)

def create_anonymous_voting(message):
    anonymous_voting.start_create_voting(message)

def show_roles_as_buttons(message):
    global role_id_to_role_name_cache

    markup = telebot.types.InlineKeyboardMarkup()
    description, response = query_db("SELECT * FROM roles", None)
    i = 1
    role_id_to_role_name_cache = dict()
    for elem in response:
        markup.add(telebot.types.InlineKeyboardButton(text=elem[1], callback_data=elem[0]))
        role_id_to_role_name_cache[elem[0]] = elem[1]
        i += 1
    bot.send_message(message.chat.id, text=localization.DownPointing, reply_markup=markup)


def show_task_by_id(call):
    markup = telebot.types.InlineKeyboardMarkup()
    description, response = query_db("SELECT * FROM tasks WHERE TaskID = %s", (call.data,))
    if call.from_user.id == response[0][3]:
        markup.add(telebot.types.InlineKeyboardButton(text=localization.Edit, callback_data=call.data))
    formatted = (
                "№{}\n<b>{}</b>\n\n{}\n\n" + localization.Created + ": <i>{}</i>\n" + localization.Deadline + ": <i>{}</i>\n\n" + localization.Cost + ": <b>{}</b>\n\n" + localization.Author + ": <i>{}</i>\n\n").format(
        response[0][0], escape_string(response[0][1]), escape_string(response[0][2]), response[0][4], response[0][5],
        response[0][6], get_member_username_from_id(response[0][3]))
    bot.send_message(call.from_user.id, formatted, parse_mode='HTML', reply_markup=markup)

    values = response[0][7].split(' ')
    index = 0
    while index < len(values) - 1:
        bot.forward_message(call.from_user.id, values[index], values[index + 1])
        index += 2


def preview_task(task, chat_id):
    markup = telebot.types.InlineKeyboardMarkup()
    formatted = (
                "<b>{}</b>\n\n{}\n\n" + localization.Deadline + ": <i>{}</i>\n\n" + localization.Cost + ": <b>{}</b>\n\n" + localization.Author + ": <i>{}</i>\n\n").format(
        task.name, task.description, task.due_date, task.estimate, get_member_username_from_id(task.author))
    bot.send_message(chat_id, formatted, parse_mode='HTML')

    for el in task.attachments:
        bot.forward_message(chat_id, el[0], el[1])


def add_role_to_task(call):
    buffer = get_task_under_construction_swap_buffer(call.from_user.id)
    try:
        if int(call.data) not in buffer.roles:
            bot.send_message(call.from_user.id,
                             text=(localization.AddedRole + ": {}").format(role_id_to_role_name_cache[int(call.data)]))
        else:
            bot.send_message(call.from_user.id, text=localization.RoleIsAlreadyAttached)
    except:
        print("Couln't find role name matching role ID {}".format(call.data))
    buffer.roles.append(int(call.data))
    set_task_under_construction_swap_buffer(call.from_user.id, buffer)


def text_message_handler(message):
    current_menu = get_state(message.chat.id)

    if message.chat.type == 'private':
        match current_menu:
            case States.MAIN_MENU:
                main_menu_handler(message)
            case States.DEPARTMENT_SELECTION_MENU:
                department_selection_menu_handler(message)
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
            case States.CREATE_TASK_CHANGE_DUE_DATE:
                create_task(current_menu, message)
            case States.CREATE_VOTING:
                if(anonymous_voting.get_state_voting(message.chat.id) == anonymous_voting.StatesVoting.CREATE_VOTING):
                    if(message.text == localization.Back):
                        execute_cancel_menu(message)
                        return
                anonymous_voting.voting_menus_handler(message)
            case _:
                print("Invalid state {}".format(current_menu))


def execute_cancel_menu(message):
    set_state(message.chat.id, States.MAIN_MENU)
    render_main_menu(message)


def create_cancel_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton(localization.Back)
    markup.add(item1)
    return markup


def create_cancel_approve_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton(localization.Back)
    item2 = types.KeyboardButton(localization.Ok)
    markup.add(item1, item2)
    return markup


def create_edit_task_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    item1 = types.KeyboardButton(localization.TaskName)
    item2 = types.KeyboardButton(localization.TaskDescription)
    item3 = types.KeyboardButton(localization.RolesPerformers)
    item4 = types.KeyboardButton(localization.AddPerformers)
    item5 = types.KeyboardButton(localization.Deadline)
    item6 = types.KeyboardButton(localization.Attachment)
    item7 = types.KeyboardButton(localization.Estimate)
    item8 = types.KeyboardButton(localization.Back)
    item9 = types.KeyboardButton(localization.Preview)
    item10 = types.KeyboardButton(localization.Create)

    markup.add(item1, item2)
    markup.add(item3, item4)
    markup.add(item5, item6, item7)
    markup.add(item8, item9, item10)

    return markup


def create_department_selection_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton(localization.InfoDepartment)
    item2 = types.KeyboardButton(localization.CulturalDepartment)
    item3 = types.KeyboardButton(localization.ScienceDepartment)
    item4 = types.KeyboardButton(localization.ChytalkaDepartment)
    item5 = types.KeyboardButton(localization.AllDepartments)
    item6 = types.KeyboardButton(localization.Back)

    markup.add(item1, item2)
    markup.add(item3, item4)
    markup.add(item5, item6)

    return markup


def execute_create_task(task, message):
    _, response = query_db("""SELECT CreationDate
                              FROM spf_management.tasks;""", None)
    if(task.creation_date,) in response:
        query_db(
            """UPDATE spf_management.tasks
             SET TaskName = %s, TaskDescription = %s, AuthorID= %s, CreationDate= %s, DueDate= %s, Estimate= %s, Attachment= %s WHERE CreationDate = %s""",
            (task.name, task.description, task.author, task.creation_date, task.due_date, task.estimate,
             ' '.join([attachment[0] + " " + attachment[1] for attachment in task.attachments]), task.creation_date))
        return
    task.creation_date = datetime.datetime.now()
    task.author = message.from_user.id
    query_db(
        "INSERT INTO spf_management.tasks (TaskName, TaskDescription, AuthorID, CreationDate, DueDate, Estimate, Attachment) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (task.name, task.description, task.author, task.creation_date, task.due_date, task.estimate,
         ' '.join([attachment[0] + " " + attachment[1] for attachment in task.attachments])))
    send_task_to_members(task)


def send_task_to_members(task):
    print(task.roles)
    for role in task.roles:
        _, response = query_db("""SELECT MemberID
                              FROM spf_management.members_roles
                              WHERE RoleID = %s;""", (role,))
        print(response)

        for member in response:
            _, username = query_db("""SELECT Telegram 
                                FROM spf_management.members
                                WHERE MemberID = %s;""", (member[0],))
            print(member)
            print(username[0][0])

            _, ids = query_db("""SELECT UserID 
                                FROM spf_management.users_id
                                WHERE Username = %s;""", (username[0][0],))
            print(ids)

            preview_task(task, ids[0][0])



def render_optionals_menu(message):
    set_state(message.chat.id, States.CREATE_TASK_OPTIONALS)
    bot.send_message(message.chat.id, localization.RenderOptionalsMenuMessage, reply_markup=create_edit_task_menu())


def create_task(current_menu, message):
    match current_menu:
        case States.MAIN_MENU:
            set_task_under_construction(message.chat.id, Task())
            set_task_under_construction_swap_buffer(message.chat.id, Task())

            set_state(message.chat.id, States.CREATE_TASK_NAME)
            bot.send_message(message.chat.id, localization.EnterTaskName, reply_markup=create_cancel_menu())
        case States.CREATE_TASK_NAME:
            if message.text == localization.Back:
                execute_cancel_menu(message)
                return
            buffer = get_task_under_construction(message.chat.id)
            buffer.name = message.text
            set_task_under_construction(message.chat.id, buffer)
            set_state(message.chat.id, States.CREATE_TASK_DESCRIPTION)
            bot.send_message(message.chat.id, localization.EnterTaskDescription, reply_markup=create_cancel_menu())
        case States.CREATE_TASK_DESCRIPTION:
            if message.text == localization.Back:
                execute_cancel_menu(message)
                return

            buffer = get_task_under_construction(message.chat.id)
            buffer.description = message.text
            set_task_under_construction(message.chat.id, buffer)

            set_state(message.chat.id, States.CREATE_TASK_OPTIONALS)
            bot.send_message(message.chat.id, localization.RenderOptionalsMenuMessage,
                             reply_markup=create_edit_task_menu())
        case States.CREATE_TASK_CHANGE_NAME:
            if message.text == localization.Back:
                render_optionals_menu(message)
                return

            buffer = get_task_under_construction(message.chat.id)
            buffer.name = message.text
            set_task_under_construction(message.chat.id, buffer)
            render_optionals_menu(message)

        case States.CREATE_TASK_CHANGE_DESCRIPTION:
            if message.text == localization.Back:
                render_optionals_menu(message)
                return
            buffer = get_task_under_construction(message.chat.id)
            buffer.description = message.text
            set_task_under_construction(message.chat.id, buffer)
            render_optionals_menu(message)

        case States.CREATE_TASK_CHANGE_ESTIMATE:
            if message.text == localization.Back:
                render_optionals_menu(message)
                return
            buffer = get_task_under_construction(message.chat.id)

            try:
                if float(message.text) >= 0.0:
                    buffer.estimate = message.text

                    set_task_under_construction(message.chat.id, buffer)
                    render_optionals_menu(message)
                else:
                    bot.send_message(message.chat.id, localization.EnterNumber, reply_markup=create_cancel_menu())
            except ValueError:
                bot.send_message(message.chat.id, localization.EnterPositiveNumber, reply_markup=create_cancel_menu())

        case States.CREATE_TASK_CHANGE_ROLES:
            if message.text == localization.Back:
                render_optionals_menu(message)
                return

            if message.text == localization.Ok:
                buffer = get_task_under_construction(message.chat.id)
                swap_buffer = get_task_under_construction_swap_buffer(message.chat.id)
                buffer.roles = swap_buffer.roles
                swap_buffer.roles = []
                set_task_under_construction_swap_buffer(message.chat.id, swap_buffer)
                set_task_under_construction(message.chat.id, buffer)

                render_optionals_menu(message)
                return

            render_optionals_menu(message)

        case States.CREATE_TASK_CHANGE_ASSIGNEES:
            if message.text == localization.Back:
                render_optionals_menu(message)
                return

            if message.text == localization.Ok:
                buffer = get_task_under_construction(message.chat.id)
                swap_buffer = get_task_under_construction_swap_buffer(message.chat.id)
                buffer.assignees = swap_buffer.assignees
                swap_buffer.assignees = []
                set_task_under_construction_swap_buffer(message.chat.id, swap_buffer)
                set_task_under_construction(message.chat.id, buffer)

                render_optionals_menu(message)
                return

            buffer = get_task_under_construction_swap_buffer(message.chat.id)
            if message.text.startswith('@'):
                buffer.assignees.append(message.text[1:])
                bot.send_message(message.chat.id, (localization.AddedPerformer + " @{}").format(message.text[1:]),
                                 reply_markup=create_cancel_approve_menu())
            else:
                buffer.assignees.append(message.text)
                bot.send_message(message.chat.id, (localization.AddedPerformer + " @{}").format(message.text),
                                 reply_markup=create_cancel_approve_menu())

            set_task_under_construction_swap_buffer(message.chat.id, buffer)

        case States.CREATE_TASK_CHANGE_ATTACHMENT:
            if message.text == localization.Back:
                render_optionals_menu(message)
                return

            if message.text == localization.Ok:
                buffer = get_task_under_construction(message.chat.id)
                swap_buffer = get_task_under_construction_swap_buffer(message.chat.id)
                buffer.attachments = swap_buffer.attachments
                swap_buffer.attachments = []
                set_task_under_construction_swap_buffer(message.chat.id, swap_buffer)
                set_task_under_construction(message.chat.id, buffer)

                render_optionals_menu(message)
                return

            buffer = get_task_under_construction_swap_buffer(message.chat.id)
            buffer.attachments.append([str(message.chat.id), str(message.message_id)])
            set_task_under_construction_swap_buffer(message.chat.id, buffer)

        case States.CREATE_TASK_CHANGE_DUE_DATE:
            if message.text == localization.Back:
                render_optionals_menu(message)
                return
            buffer = get_task_under_construction(message.chat.id)

            try:
                datetime.datetime.strptime(message.text, '%Y-%m-%d %H:%M:%S')
                buffer.due_date = message.text

                set_task_under_construction(message.chat.id, buffer)
                render_optionals_menu(message)
            except ValueError:
                bot.send_message(message.chat.id, localization.EnterDateInFormat, reply_markup=create_cancel_menu())

        case States.CREATE_TASK_OPTIONALS:
            if message.text == localization.TaskName:
                set_state(message.chat.id, States.CREATE_TASK_CHANGE_NAME)
                bot.send_message(message.chat.id, localization.EnterTaskName, reply_markup=create_cancel_menu())
                return

            if message.text == localization.TaskDescription:
                set_state(message.chat.id, States.CREATE_TASK_CHANGE_DESCRIPTION)
                bot.send_message(message.chat.id, localization.EnterTaskDescription, reply_markup=create_cancel_menu())
                return

            if message.text == localization.Estimate:
                set_state(message.chat.id, States.CREATE_TASK_CHANGE_ESTIMATE)
                bot.send_message(message.chat.id, localization.EnterEstimate, reply_markup=create_cancel_menu())
                return

            if message.text == localization.RolesPerformers:
                set_state(message.chat.id, States.CREATE_TASK_CHANGE_ROLES)
                bot.send_message(message.chat.id, localization.ChooseRolesPerformers,
                                 reply_markup=create_cancel_approve_menu())
                show_roles_as_buttons(message)
                return

            if message.text == localization.Deadline:
                set_state(message.chat.id, States.CREATE_TASK_CHANGE_DUE_DATE)
                bot.send_message(message.chat.id, localization.EnterDeadlineInFormat, reply_markup=create_cancel_menu())
                return

            if message.text == localization.AddPerformers:
                set_state(message.chat.id, States.CREATE_TASK_CHANGE_ASSIGNEES)
                bot.send_message(message.chat.id, localization.EnterNicknamesPerformers,
                                 reply_markup=create_cancel_approve_menu())
                return

            if message.text == localization.Attachment:
                set_state(message.chat.id, States.CREATE_TASK_CHANGE_ATTACHMENT)
                bot.send_message(message.chat.id, localization.SendAttachment,
                                 reply_markup=create_cancel_approve_menu())
                return

            if message.text == localization.Back:
                execute_cancel_menu(message)
                return

            if message.text == localization.Preview:
                task = get_task_under_construction(message.chat.id)
                task.author = get_member_username_from_id(message.from_user.id)
                set_task_under_construction(message.chat.id, task)
                preview_task(task, message.chat.id)
                return

            if message.text == localization.Create:
                execute_create_task(get_task_under_construction(message.chat.id), message)
                set_state(message.chat.id, States.MAIN_MENU)
                render_main_menu(message)
                set_task_under_construction(message.chat.id, Task())
                set_task_under_construction_swap_buffer(message.chat.id, Task())

                return

            render_optionals_menu(message)

def edit_task(call):
    _, response = query_db("SELECT * FROM tasks WHERE TaskID = %s", (call.data,))
    to_edit = Task()
    to_edit.name=response[0][1]
    to_edit.description=response[0][2]
    to_edit.creation_date=response[0][4]
    to_edit.due_date=response[0][5]
    to_edit.estimate=response[0][6]
    to_edit.author=response[0][3]
    set_task_under_construction(call.message.chat.id, to_edit)
    render_optionals_menu(call.message)
    

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
        set_task_under_construction_swap_buffer(message.chat.id, swap_buffer)

@bot.message_handler(func=lambda message: True)
def reply_to_message(message):
    print("Reply to message: {}".format(message.text))
    text_message_handler(message)

@bot.callback_query_handler(func=lambda call: True)
def query_handler(call):
    print("Callback query handler: {}".format(call.data))
    print(call.message.text.split('\n')[0])
    match call.message.text.split('\n')[0]:
        case localization.ChooseTask:
            show_task_by_id(call)
        case localization.DownPointing:  # TODO: ???
            add_role_to_task(call)
        case text if text.startswith('№'):
            edit_task(call)
            
    if call.data.startswith('register_user_voting'):
        user_id = call.from_user.id
        creator_id = call.data.split('/')[1]
        anonymous_voting.add_participant_voting(creator_id, user_id)
    if call.data.startswith('voting_chat'):
        chat_id = call.data.split('/')[1]
        anonymous_voting.set_voting_chat_id(call.message, chat_id)
        
@bot.message_handler(content_types=["poll"])
def poll_handler(message: types.Message):
    if(anonymous_voting.get_state_voting(message.chat.id) == anonymous_voting.StatesVoting.CREATE_VOTING_POLL):
        anonymous_voting.create_voting_poll_handler(message)

bot.infinity_polling()
