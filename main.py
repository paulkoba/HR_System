import telebot
import datetime
import localization
from states import States
from telebot import types
from prettytable import PrettyTable
from KEYS import *
from utils import *
from database import query_db
from task import Task
from local_task_store import get_task_under_construction, get_task_under_construction_swap_buffer, \
    set_task_under_construction, set_task_under_construction_swap_buffer
import traceback

role_id_to_role_name_cache = dict()

def is_current_user_administrator(id):
    try:
        username = get_member_username_from_id(id)
        print(username)
        _, response = query_db("SELECT MemberID FROM members WHERE Telegram = %s", (username,))
        _, response = query_db("SELECT * FROM administrators WHERE MemberID = %s", (response[0][0],))
        print("Verifying that the current user {} is an administrator: {}".format(id, len(response)))
        return len(response) >= 1
    except:
        print(traceback.format_exc())
        print("Couldn't verify user {} as an administrator".format(id))
        pass
    return False

def get_member_username_from_id(id):
    _, response = query_db("SELECT * FROM users_id WHERE UserID = %s", (id,))

    if len(response) == 0:
        print("Couldn't retrieve username of user with ID: {}".format(id))
        return str(id)

    return response[0][1]


def get_member_id_from_id(id):
    _, response = query_db("SELECT MemberID FROM users_id WHERE UserID = %s", (id,))

    if len(response) == 0:
        print("Couldn't retrieve username of user with ID: {}".format(id))
        return str(id)

    return response[0][0]

def get_full_name_from_member_id(id):
    _, response = query_db("SELECT Name, Surname FROM members WHERE MemberID = %s", (id,))

    if len(response) == 0:
        print("Couldn't retrieve username of user with ID: {}".format(id))
        return "None"

    return response[0][0] + " " + response[0][1]

def get_id_from_member_id(id):
    _, response = query_db("SELECT Telegram FROM members WHERE MemberID = %s", (id,))
    
    if len(response) == 0:
        print("Couldn't retrieve telegram username of user with MemberID: {}".format(id))
        return str(id)

    _, response1 = query_db("SELECT UserID FROM users_id WHERE Username = %s", (response[0][0],))

    if len(response1) == 0:
        print("Couldn't retrieve UserID of user with Username: {}".format(response[0][0]))
        return str(id)

    return response1[0][0]

def update_id_username_relation(message):
    _, response = query_db("SELECT * FROM users_id WHERE UserID = %s", (message.from_user.id,))

    if response:
        query_db("UPDATE users_id SET Username = @%s WHERE UserID = %s",
                 (message.from_user.username, message.from_user.id))
    else:
        query_db("INSERT INTO users_id (UserID, Username) VALUES (%s, @%s)",
                 (message.from_user.id, message.from_user.username))

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

edited_users = dict()

def set_currently_edited_user(chat_id, user):
    print("Setting currently edited user in chat {} to {}".format(chat_id, user))
    edited_users[chat_id] = user

def get_currently_edited_user(chat_id):
    return edited_users[chat_id]

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

def make_main_menu(is_administrator):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    item0 = types.KeyboardButton(localization.ViewProfile)
    item00 = types.KeyboardButton(localization.EditProfile)
    item1 = types.KeyboardButton(localization.CreateTask)
    item2 = types.KeyboardButton(localization.ViewTasks)
    item3 = types.KeyboardButton(localization.ViewMyTasks)
    item4 = types.KeyboardButton(localization.ReportError)
    
    if is_administrator:
        markup.add(item0, item00)
    else:
        markup.add(item0)

    if is_administrator:
        markup.add(item1, item2, item3)
    else:
        markup.add(item2, item3)
    
    markup.add(item4)
    return markup

def preview_profile(chat_id, id):
    username = get_member_username_from_id(id)
    _, response = query_db("SELECT * FROM members WHERE Telegram = %s", (username,))
    managerName = get_full_name_from_member_id(response[0][7])
    administrator = "Yes" if is_current_user_administrator(id) else "No"
    bot.send_message(chat_id, localization.ProfileString.format(response[0][1], response[0][2], response[0][3], response[0][4], response[0][5], response[0][6], managerName, administrator))

def main_menu_handler(message):
    set_state(message.chat.id, States.MAIN_MENU)
    if message.text == localization.CreateTask:
        create_task(get_state(message.chat.id), message)
    elif message.text == localization.ViewTasks:
        show_tasks_as_buttons(message, False)
    elif message.text == localization.ViewMyTasks:
        show_tasks_as_buttons(message, True)
    elif message.text == localization.ReportError:
        set_state(message.from_user.id, States.REPORTING_ISSUE)
        bot.send_message(message.chat.id, localization.NothingWorks)
    elif message.text == localization.ViewProfile:
        preview_profile(message.chat.id, message.from_user.id)
    elif message.text == localization.EditProfile:
        edit_user(get_state(message.chat.id), message)
    else:
        print("Received message \"{}\" in main_menu_handler".format(message.text))

def render_main_menu(message):
    markup = make_main_menu(is_current_user_administrator(message.from_user.id))

    update_id_username_relation(message)

    bot.send_message(message.chat.id, localization.ChooseAction, reply_markup=markup)


def show_tasks_as_buttons(message, filter_by_user=False):
    markup = telebot.types.InlineKeyboardMarkup()
    if filter_by_user:
        _, response = query_db("SELECT tasks.* FROM tasks JOIN users_tasks ON tasks.TaskID = users_tasks.TaskID WHERE users_tasks.ID = %s; ", (message.from_user.id,))
    else:
        _, response = query_db("SELECT * FROM tasks", None)

    if response != [] :
        i = 1
        for elem in response:
            markup.add(telebot.types.InlineKeyboardButton(text=elem[1], callback_data=elem[0]))
            i += 1
        bot.send_message(message.chat.id, text=localization.ChooseTask, reply_markup=markup)
    else :
        bot.send_message(message.chat.id, text=localization.NoTasks)

def show_roles_as_buttons(message):
    global role_id_to_role_name_cache

    markup = telebot.types.InlineKeyboardMarkup()
    _, response = query_db("SELECT * FROM job_titles", None)
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
    if call.from_user.id == response[0][3] or is_current_user_administrator(call.from_user.id):
        markup.add(telebot.types.InlineKeyboardButton(text=localization.Edit, callback_data=call.data))
    formatted = (
                "№{}\n<b>{}</b>\n\n{}\n\n" + localization.Created + ": <i>{}</i>\n" + localization.Deadline + ": <i>{}</i>\n\n" + localization.Cost + ": <b>{}</b>\n\n" + localization.Author + ": <i>{}</i>\n\n").format(
        response[0][0], escape_string(response[0][1]), escape_string(response[0][2]), response[0][4], response[0][5],
        response[0][6], get_member_username_from_id(response[0][3]))
    
    assignees = get_list_of_assignees_for_task(response[0][0])
    if assignees:
        formatted += localization.Assignees + ": {}\n\n".format(", ".join(assignees))

    bot.send_message(call.from_user.id, formatted, parse_mode='HTML', reply_markup=markup)

    values = response[0][7].split(' ')
    index = 0
    while index < len(values) - 1:
        bot.forward_message(call.from_user.id, values[index], values[index + 1])
        index += 2


def preview_task(task, chat_id):
    markup = telebot.types.InlineKeyboardMarkup()

    formatted = (
                "<b>{}</b>\n\n{}\n\n" + localization.Deadline + ": <i>{}</i>\n\n" + localization.Cost + ": <b>{}</b>\n\n" + localization.Author + ": <i>{}</i>\n\n" + localization.Assignees + ": {}\n\n").format(
        task.name, task.description, task.due_date, task.estimate, get_member_username_from_id(task.author), ", ".join(['@' + assignee for assignee in task.assignees]) if not task.assignees  == "" else localization.LocalizationNone)

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
            case States.EDIT_USER_OPTIONALS:
                edit_user(current_menu, message)
            case States.EDIT_USER_OPTIONALS_USER_SELECTED:
                edit_user(current_menu, message)
            case States.EDIT_USER_MANAGER:
                edit_user(current_menu, message)
            case States.EDIT_USER_NAME:
                edit_user(current_menu, message)
            case States.EDIT_USER_PHONE:
                edit_user(current_menu, message)
            case States.EDIT_USER_SURNAME:
                edit_user(current_menu, message)
            case States.EDIT_USER_PREVIEW:
                edit_user(current_menu, message)
            case States.REPORTING_ISSUE:
                set_state(message.from_user.id, States.MAIN_MENU)
                query_db("INSERT INTO issues (ReporterID, Description) VALUES (%s, %s)", (message.from_user.id, message.text))
                bot.send_message(message.chat.id, "Your issue was reported to an administrator.", reply_markup=make_main_menu(is_current_user_administrator(message.from_user.id)))
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

def create_edit_user_list(message):
    markup = telebot.types.InlineKeyboardMarkup()
    _, response = query_db("SELECT * FROM members", None)
    
    if response != [] :
        i = 1
        for elem in response:
            markup.add(telebot.types.InlineKeyboardButton(text=elem[1] + " " + elem[2], callback_data=elem[0]))
            i += 1
        bot.send_message(message.chat.id, text=localization.DownPointing, reply_markup=markup)
    else :
        bot.send_message(message.chat.id, text=localization.NoTasks)

def create_edit_user_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    item1 = types.KeyboardButton(localization.EditUserName)
    item2 = types.KeyboardButton(localization.EditUserSurname)
    item3 = types.KeyboardButton(localization.EditUserManager)
    item4 = types.KeyboardButton(localization.EditUserPhone)
    item5 = types.KeyboardButton(localization.EditUserPreview)
    item6 = types.KeyboardButton(localization.Back)

    markup.add(item1, item2)
    markup.add(item3, item4)
    markup.add(item5, item6)

    return markup

def show_edit_user(message):
    bot.send_message(message.chat.id, localization.ValueToEdit, reply_markup=create_edit_user_menu())
    set_state(message.from_user.id, States.EDIT_USER_OPTIONALS_USER_SELECTED)

def enter_edit_user(call):
    bot.send_message(call.message.chat.id, localization.ValueToEdit, reply_markup=create_edit_user_menu())
    set_currently_edited_user(call.from_user.id, call.data)
    set_state(call.from_user.id, States.EDIT_USER_OPTIONALS_USER_SELECTED)

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

def execute_create_task(task, message):
    if not is_current_user_administrator(message.from_user.id):
        bot.send_message(message.chat.id, localization.AntiAdministratorSpoofingMessage)
        return

    _, response = query_db("""SELECT CreationDate
                              FROM tasks;""", None)
    if(task.creation_date,) in response:
        query_db(
            """UPDATE tasks
             SET TaskName = %s, TaskDescription = %s, AuthorID= %s, CreationDate= %s, DueDate= %s, Estimate= %s, Attachment= %s WHERE CreationDate = %s""",
            (task.name, task.description, task.author, task.creation_date, task.due_date, task.estimate,
             ' '.join([attachment[0] + " " + attachment[1] for attachment in task.attachments]), task.creation_date))
        return
    task.creation_date = datetime.datetime.now()
    task.author = message.from_user.id
    _, response = query_db(
        "INSERT INTO tasks (TaskName, TaskDescription, AuthorID, CreationDate, DueDate, Estimate, Attachment) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (task.name, task.description, task.author, task.creation_date, task.due_date, task.estimate,
         ' '.join([attachment[0] + " " + attachment[1] for attachment in task.attachments])))
    description, task_id = query_db("SELECT LAST_INSERT_ID() AS last_id", None)
    print (task.assignees)
    for assignee in task.assignees:
        user_id = get_id_from_username(assignee)
        if user_id:
            print("Inserting", user_id, task_id[0][0])
            query_db("INSERT INTO users_tasks (ID, TaskID) VALUES (%s, %s)", (user_id, task_id[0][0]))
    send_task_to_members(task)


def send_task_to_members(task):
    print(task.roles)
    for role in task.roles:
        _, response = query_db("""SELECT MemberID
                              FROM members_job_titles
                              WHERE RoleID = %s;""", (role,))
        print(response)

        for member in response:
            _, username = query_db("""SELECT Telegram 
                                FROM members
                                WHERE MemberID = %s;""", (member[0],))
            print(member)
            print(username[0][0])

            _, ids = query_db("""SELECT UserID 
                                FROM users_id
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

def handle_edit_user_optionals_choice(message):
    match message.text:
        case localization.EditUserName:
            set_state(message.from_user.id, States.EDIT_USER_NAME)
            bot.send_message(message.chat.id, localization.FullEditUserName)
        case localization.EditUserSurname:
            set_state(message.from_user.id, States.EDIT_USER_SURNAME)
            bot.send_message(message.chat.id, localization.FullEditUserSurname)
        case localization.EditUserPhone:
            set_state(message.from_user.id, States.EDIT_USER_PHONE)
            bot.send_message(message.chat.id, localization.FullEditUserPhone)
        case localization.EditUserManager:
            set_state(message.from_user.id, States.EDIT_USER_MANAGER)
            bot.send_message(message.chat.id, localization.NothingWorks)
        case localization.EditUserPreview:
            preview_profile(message.chat.id, get_id_from_member_id(get_currently_edited_user(message.chat.id)))
        case localization.Back:
            set_state(message.chat.id, States.MAIN_MENU)
            render_main_menu(message)

def edit_user(current_menu, message):
    if message.text == localization.Back:
        execute_cancel_menu(message)

    match current_menu:
        case States.MAIN_MENU:
            set_state(message.chat.id, States.EDIT_USER_OPTIONALS)
            bot.send_message(message.chat.id, localization.ChooseTask, reply_markup=create_cancel_menu())
            create_edit_user_list(message)
        case States.EDIT_USER_OPTIONALS_USER_SELECTED:
            handle_edit_user_optionals_choice(message)
        case States.EDIT_USER_NAME:
            query_db("UPDATE members SET Name = %s WHERE MemberID = %s", (message.text, get_currently_edited_user(message.chat.id)))
            show_edit_user(message)
        case States.EDIT_USER_SURNAME:
            query_db("UPDATE members SET Surname = %s WHERE MemberID = %s", (message.text, get_currently_edited_user(message.chat.id)))
            show_edit_user(message)
        case States.EDIT_USER_PHONE:
            query_db("UPDATE members SET Phone = %s WHERE MemberID = %s", (message.text, get_currently_edited_user(message.chat.id)))
            show_edit_user(message)
        case _:
            print("Unknown state: " + str(current_menu))
            
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
        case localization.DownPointing:
            if get_state(call.message.chat.id) == States.EDIT_USER_OPTIONALS:
                enter_edit_user(call)
            else:
                add_role_to_task(call)
        case text if text.startswith('№'):
            edit_task(call)
            
bot.infinity_polling()
