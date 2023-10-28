import telebot
import localization
from enum import Enum
from database import query_db
from KEYS import *
from telebot import types

bot = telebot.TeleBot(TOKEN)

def start_create_voting(message):
    set_state_voting(message.chat.id, StatesVoting.CREATE_VOTING)
    render_voting_creation_menu(message)

class StatesVoting(Enum):
    CREATE_VOTING = 1
    CHOOSE_VOTING_CHAT = 2
    EDIT_VOTING_MEMBERS = 3
    CREATE_VOTING_POLL = 4
    CREATE_VOTING_POLL_CONFIRMATION = 5

def get_state_voting(creator_id):
    _, response = query_db("SELECT State FROM anonymous_votings WHERE CreatorID = %s", (creator_id,))

    if len(response) == 0:
        set_state_voting(creator_id, StatesVoting.CREATE_VOTING)
        _, response = query_db("SELECT State FROM anonymous_votings WHERE CreatorID = %s", (creator_id,))

    print("Received state {}".format(response[0][0]))
    return StatesVoting(response[0][0])


def set_state_voting(creator_id, state):
    print("Setting state to {}".format(state))
    _, response = query_db("SELECT * FROM anonymous_votings WHERE CreatorID = %s", (creator_id,))
    if response:
        query_db("UPDATE anonymous_votings SET State = %s WHERE CreatorID = %s", (state.value, creator_id))
    else:
        query_db("INSERT INTO anonymous_votings (CreatorID, State) VALUES (%s, %s)", (creator_id, state.value))


def voting_menus_handler(message):
    current_menu = get_state_voting(message.chat.id)

    if message.chat.type == 'private':
        match current_menu:
            case StatesVoting.CREATE_VOTING:
                voting_creation_menu_handler(message)
            case StatesVoting.CHOOSE_VOTING_CHAT:
                if(message.text == localization.Back):
                    return_to_voting_creation_menu(message)
            case StatesVoting.EDIT_VOTING_MEMBERS:
                edit_voting_participants_handler(message)
            case StatesVoting.CREATE_VOTING_POLL:
                if(message.text == localization.Back):
                    return_to_voting_creation_menu(message)
            case StatesVoting.CREATE_VOTING_POLL_CONFIRMATION:
                create_voting_poll_confirmation_handler(message)
            case _:
                print("Invalid state {}".format(current_menu))

def render_voting_creation_menu(message):
    markup = make_voting_creation_menu()
    bot.send_message(message.chat.id, localization.ChooseAction, reply_markup=markup)

def make_voting_creation_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton(localization.ChooseRegistrationChat)
    item2 = types.KeyboardButton(localization.CreateRegistrationButton)
    item3 = types.KeyboardButton(localization.ViewAllVotingMembers)
    item4 = types.KeyboardButton(localization.EditVotingMembers)
    item5 = types.KeyboardButton(localization.CreateVoting)
    item6 = types.KeyboardButton(localization.Back)
    markup.add(item1, item2)
    markup.add(item3, item4)
    markup.add(item5, item6)
    return markup

def render_back_menu(message, messageText):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton(localization.Back)
    markup.add(item1)
    bot.send_message(message.chat.id, messageText, reply_markup=markup)

def voting_creation_menu_handler(message):
    if message.text == localization.ChooseRegistrationChat:
        set_state_voting(message.chat.id, StatesVoting.CHOOSE_VOTING_CHAT)
        choose_voting_chat(message)
    elif message.text == localization.CreateRegistrationButton:
        create_register_voting_button(message, localization.RegisterButtonTitle)
    elif message.text == localization.ViewAllVotingMembers:
        show_all_voting_members(message)
    elif message.text == localization.EditVotingMembers:
        show_all_voting_members(message)
        render_back_menu(message, localization.IDParticipantToDelete)
        set_state_voting(message.chat.id, StatesVoting.EDIT_VOTING_MEMBERS)
    elif message.text == localization.CreateVoting:
        set_state_voting(message.chat.id, StatesVoting.CREATE_VOTING_POLL)
        render_back_menu(message, localization.SendVotingPoll)
    else:
        print("Received message \"{}\" in voting_creation_menu_handler".format(message.text))

def return_to_voting_creation_menu(message):
    set_state_voting(message.chat.id, StatesVoting.CREATE_VOTING)
    render_voting_creation_menu(message) 

def show_chats_as_buttons(message):
    markup = telebot.types.InlineKeyboardMarkup()
    description, response = query_db("SELECT * FROM group_chats", None)
    i = 1
    for elem in response:
        markup.add(telebot.types.InlineKeyboardButton(text=str(elem[1]) +" ("+str(elem[2])+")", callback_data="voting_chat/"+str(elem[0])))
        i += 1
    bot.send_message(message.chat.id, text=localization.ChatsList, reply_markup=markup)

def get_chat_info(chat_id):
    markup = telebot.types.InlineKeyboardMarkup()
    _, response = query_db("SELECT * FROM group_chats WHERE ChatID = %s", (chat_id,))
    return str(response[0][1]) +" ("+str(response[0][2])+")"

def choose_voting_chat(message):
    show_chats_as_buttons(message)
    render_back_menu(message, localization.ChooseChatWarning)

def set_voting_chat_id(message, chat_id):
    create_voting_delete_previous(message.chat.id)
    set_voting_chat(message.chat.id, chat_id)
    bot.send_message(message.chat.id, localization.RecievedChat + " "+get_chat_info(chat_id))
    return_to_voting_creation_menu(message)

def edit_voting_participants_handler(message):
    if(message.text == localization.Back):
        return_to_voting_creation_menu(message)
        return
    result = delete_voting_participant(message.chat.id, message.text)
    if(result):
        bot.send_message(message.chat.id, localization.ParticipantDeleted+" "+get_user_info_by_id(message.text))
        bot.send_message(message.chat.id, localization.IDParticipantToDelete)
    else:
        bot.send_message(message.chat.id, localization.IncorrectId)
        bot.send_message(message.chat.id, localization.IDParticipantToDelete)

def delete_voting_participant(creator_id, user_id):
    _, response = query_db("SELECT * FROM anonymous_votings_participants WHERE CreatorID = %s AND UserID = %s", (creator_id, user_id))
    if response:
        query_db("DELETE FROM anonymous_votings_participants WHERE CreatorID = %s AND UserID = %s", (creator_id, user_id))
        return True
    else:
        return False
    
def create_voting_delete_previous(creator_id):
    state = get_state_voting(creator_id)
    #delete_voting(creator_id)
    delete_voting_participants(creator_id)
    
    _, response = query_db("SELECT * FROM anonymous_votings WHERE CreatorID = %s", (creator_id, ))
    if len(response) == 0:
        query_db("INSERT INTO anonymous_votings (CreatorID, State) VALUES (%s)", (creator_id, state.value))

def delete_voting(creator_id):
    _, response = query_db("SELECT * FROM anonymous_votings WHERE CreatorID = %s", (creator_id,))
    if response:
        query_db("DELETE FROM anonymous_votings WHERE CreatorID = %s", (creator_id,))
        
def delete_voting_participants(creator_id):
    _, response = query_db("SELECT * FROM anonymous_votings_participants WHERE CreatorID = %s", (creator_id,))
    if response:
        query_db("DELETE FROM anonymous_votings_participants WHERE CreatorID = %s", (creator_id,))
      
def set_voting_chat(creator_id, chat_id):
    _, response = query_db("SELECT * FROM anonymous_votings WHERE CreatorID = %s", (creator_id, ))
    if response:
        query_db("UPDATE anonymous_votings SET ChatID = %s WHERE CreatorID = %s", (chat_id, creator_id))
    else:
        query_db("INSERT INTO anonymous_votings (CreatorID, ChatID) VALUES (%s)", (creator_id, chat_id))  

def create_register_voting_button(message, message_text):
    chat_id = get_voting_chat(message.chat.id)
    if(chat_id == None):
        bot.send_message(message.chat.id, localization.NoVotingChat)
        return
    markup = telebot.types.InlineKeyboardMarkup()
    button_text = localization.TakePartInVoting
    button = telebot.types.InlineKeyboardButton(button_text, callback_data='register_user_voting/'+str(message.chat.id))
    markup.add(button)
    bot.send_message(chat_id, message_text, reply_markup=markup)

def get_voting_chat(creator_id):
    _, response = query_db("SELECT ChatID FROM anonymous_votings WHERE CreatorID = %s", (creator_id,))

    if len(response) == 0:
        return None
    print("Received chat id {}".format(response[0][0]))
    return response[0][0]

def show_all_voting_members(message):
    user_ids = get_voting_participants_ids(message.chat.id)
    users_info = ""
    for user_id in user_ids:
        users_info += get_user_info_by_id(user_id[0]) + "\n"
    bot.send_message(message.chat.id, localization.ListOfAllVotingMembers + f'\n{users_info}')

def get_user_info_by_id(user_id):
    try:
        user_info = bot.get_chat(user_id)
        first_name = user_info.first_name or ""
        last_name = user_info.last_name or ""
        username = user_info.username or ""
        if(username != ""):
            username = "@"+username
        return str(first_name)+" "+str(last_name)+" "+str(username)+",  id:"+str(user_id)
    except:
        return localization.UndefinedUser

def add_participant_voting(creator_id, user_id):
    _, response = query_db("SELECT * FROM anonymous_votings_participants WHERE CreatorID = %s AND UserID = %s", (creator_id, user_id))
    if len(response) == 0:
        query_db("INSERT INTO anonymous_votings_participants (CreatorID, UserID) VALUES (%s, %s)", (creator_id, user_id))
       
def create_voting_poll_handler(message):
    set_voting_message(message.chat.id, message.id)
    set_state_voting(message.chat.id, StatesVoting.CREATE_VOTING_POLL_CONFIRMATION)
    render_confirmation_menu(message, localization.YourMessageVotingPoll)

def set_voting_message(creator_id, voting_message_id):
    _, response = query_db("SELECT * FROM anonymous_votings WHERE CreatorID = %s", (creator_id, ))
    if response:
        query_db("UPDATE anonymous_votings SET VotingMessageID = %s WHERE CreatorID = %s", (voting_message_id, creator_id))
    else:
        query_db("INSERT INTO anonymous_votings (CreatorID, VotingMessageID) VALUES (%s)", (creator_id, voting_message_id))

def render_confirmation_menu(message, message_text):
    markup = create_confirmation_menu()
    bot.send_message(message.chat.id, message_text, reply_markup=markup)

def create_confirmation_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton(localization.Ok)
    item2 = types.KeyboardButton(localization.Back)
    markup.add(item1, item2)
    return markup

def create_voting_poll_confirmation_handler(message):
    set_state_voting(message.chat.id, StatesVoting.CREATE_VOTING_POLL_CONFIRMATION)
    if message.text == localization.Ok:
        send_voting_poll(message)
        bot.send_message(message.chat.id, localization.VotingSend)
        return_to_voting_creation_menu(message)
    elif message.text == localization.Back:
        bot.send_message(message.chat.id, localization.CancelledVotingSend)
        return_to_voting_creation_menu(message)
    else:
        bot.send_message(message.chat.id, localization.CancelledVotingSend)
        return_to_voting_creation_menu(message)  

def send_voting_poll(message):
    user_ids = get_voting_participants_ids(message.chat.id)
    poll_message_id = get_voting_message_id(message.chat.id)
    if(poll_message_id == None):
        bot.send_message(message.chat.id, localization.NoVotingMessage)
        return_to_voting_creation_menu(message)
        return
    for user_id in user_ids:
        try:
            bot.forward_message(user_id, message.chat.id, poll_message_id)
        except:
            bot.send_message(message.chat.id, localization.UserDoesntHaveChat+"\n" + get_user_info_by_id(user_id))
            

def get_voting_message_id(creator_id):
    _, response = query_db("SELECT VotingMessageID FROM anonymous_votings WHERE CreatorID = %s", (creator_id,))

    if len(response) == 0:
        return None
    print("Received voting message id {}".format(response[0][0]))
    return response[0][0]

def get_voting_participants_ids(creator_id):
    _, response = query_db("SELECT UserID FROM anonymous_votings_participants WHERE CreatorID = %s", (creator_id,))
    return response
