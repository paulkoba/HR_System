from database import query_db
import traceback

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

def get_id_from_username(username):
    description, response = query_db("SELECT * FROM users_id WHERE Username = \"%s\" ", ('@' + username,))
    print("Description:", description)
    print("Response:", response)
    if len(response) == 0:
        print("Couldn't retrieve ID for user with Username: {}".format('@' + username))
        return None  # You might want to handle this case differently based on your requirements
    
    return response[0][0]  # Assuming UserID is in the first position in the response


def get_full_name_from_member_id(id):
    _, response = query_db("SELECT Name, Surname FROM members WHERE MemberID = %s", (id,))

    if len(response) == 0:
        print("Couldn't retrieve username of user with ID: {}".format(id))
        return str(id)

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

def get_list_of_assignees_for_task(id):
    _, response = query_db("SELECT ID FROM users_tasks WHERE TaskID = %s", (id,))
    
    return [get_member_username_from_id(el[0]) for el in response]