import mysql.connector 
import threading
from mysql.connector import Error
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

lock = threading.Lock()
connection = create_connection(IP, USERNAME, PASSWORD, "hr_system")

def query_db(query, parameters):
    global lock
    lock.acquire()
    cursor = connection.cursor()

    try:
        if parameters is None:
            cursor.execute(query)
        else:
            cursor.execute(query, parameters)

        description = cursor.description
        
        a, b = description, cursor.fetchall()
        lock.release()
        return a, b

    except Error as e :
        print(f"The error '{e}' occurred")
    
    lock.release()