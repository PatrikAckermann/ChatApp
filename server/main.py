import socket
import threading
import json
import time
import sqlite3
from sqlite3 import Error
import hashlib

class user:
    def __init__(self, username, conn, addr):
        self.username = username
        self.conn = conn
        self.addr = addr

class accountDatabase:
    def __init__(self):
        try:
            self.conn = sqlite3.connect("accounts.db", check_same_thread=False)
        except Error as e:
            print(f"Couldn't connect to database:\n{e}")
        try:
            self.c = self.conn.cursor()
            self.c.execute(""" CREATE TABLE IF NOT EXISTS accounts (
            id integer PRIMARY KEY,
            username text,
            password text
            ); """)
        except Error as e:
            print(f"Couldn't create or load table:\n{e}")
    
    def addAccount(self, username, password): #1. Need to check if user is already in database
        if self.checkUsername(username) == False:
            if username[0].isnumeric() == False:
                if username.isalnum() == True:
                    hashedPw = hashlib.sha3_256(password.encode()).hexdigest()
                    self.c.execute(""" INSERT INTO accounts(username, password)
                    VALUES(?,?) """, (username,hashedPw))
                    self.conn.commit()
                    return {"success": True}
                else:
                    return {"success": False, "error":"notAlphanumeric"}
            else:
                return {"success": False, "error":"numbersOnly"}
        else:
            return {"success": False, "error":"usernameTaken"}
    
    def changePassword(self, username, newPw):
        hashedPw = hashlib.sha3_256(newPw.encode()).hexdigest()
        self.c.execute(""" UPDATE accounts
        SET password = ?
        WHERE username = ?
        """, (hashedPw, username))
        self.conn.commit()
    
    def checkUsername(self, username):
        self.c.execute("SELECT username FROM accounts WHERE username=?", (username,))
        result = self.c.fetchone()
        if result:
            return True
        else:
            return False

    def checkPassword(self, username, password):
        hashedPw = hashlib.sha3_256(password.encode()).hexdigest()
        self.c.execute("SELECT password FROM accounts WHERE username=? AND password=?", (username,hashedPw))
        result = self.c.fetchone()
        if result:
            return True
        else:
            return False
    
class messageDatabase:
    def __init__(self):
        try:
            self.conn = sqlite3.connect("messages.db", check_same_thread=False)
            self.c = self.conn.cursor()
        except Error as e:
            print(f"Couldn't connect to database:\n{e}")
        self.c.execute("CREATE TABLE IF NOT EXISTS chatlist (id integer PRIMARY KEY, combinedName text, user1 text, user2 text)")
    
    def getTableName(self, name1, name2):
        sort = sorted([name1, name2])
        return sort[0] + "_" + sort[1]

    def addTable(self, name1, name2):
        string = f"CREATE TABLE IF NOT EXISTS {self.getTableName(name1, name2)} (id integer PRIMARY KEY, sender text, message text, sent integer)"
        self.c.execute("INSERT INTO chatlist(combinedName, user1, user2) VALUES(?,?,?)", (self.getTableName(name1, name2), name1, name2))
        print(string)
        self.c.execute(string)
        self.conn.commit()
    
    def deleteTable(self, name1, name2):
        self.c.execute(f"DROP TABLE IF EXISTS {self.getTableName(name1, name2)}")
        self.c.execute(f"DELETE FROM chatlist WHERE combinedName==?", (self.getTableName(name1, name2),))
        self.conn.commit()
    
    def checkTable(self, name1, name2):
        self.c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (self.getTableName(name1, name2),))
        result = self.c.fetchone()
        if result:
            return True
        else:
            return False
    
    def countMessages(self, name1, name2):
        if self.checkTable(name1, name2):
            self.c.execute(f"SELECT * FROM {self.getTableName(name1, name2)}")
            result = self.c.fetchall()
            return len(result)
        return 0
    
    def addMessage(self, sender, receiver, message, sent=1):
        self.c.execute(f"INSERT INTO {self.getTableName(receiver, sender)}(sender, message, sent) VALUES(?,?,?)", (sender, message, sent))
        self.conn.commit()
    
    def loadMessages(self, name1, name2, fromId):
        self.c.execute(f"SELECT * FROM {self.getTableName(name1, name2)} limit {fromId - 1}, 9999999")
        results = self.c.fetchall()
        return results
    
    def getChatsOfUser(self, username):
        output = []
        self.c.execute("SELECT combinedName FROM chatlist WHERE user1=? OR user2=?", (username, username))
        results = self.c.fetchall()
        for chat in results:
            output.append(chat[0])
        return output
    
    def getUnsentMessages(self, username):
        output = []
        for chat in self.getChatsOfUser(username):
            self.c.execute(f"SELECT id, sender, message FROM {chat} WHERE sent = 0 AND sender != ?", (username,))
            results = self.c.fetchall()
            for result in results:
                output.append([result[1], result[2], result[0], chat])
        return output
    
    def markAsSent(self, chat, id):
        self.c.execute(f"UPDATE {chat} SET sent=1 WHERE id=?", (id,))
        self.conn.commit()

clientList = []
print("Starting startup process.\nStarting database...")
messageDb = messageDatabase()
accountDb = accountDatabase()
print("Database online.\nStarting server...")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(("127.0.0.1", 5432))
s.listen()
print("Server online.\nStartup process complete. Waiting for connections...")

def getConnectedList():
    output = []
    for client in clientList:
        output.append(client.username)
    return output

def closeConnection(client):
    userlist = getConnectedList()
    for chat in messageDb.getChatsOfUser(client.username):
        chat = chat.split("_")
        if chat[0] == client.username:
            chat = chat[1]
        else:
            chat = chat[0]
        for user in clientList:
            if user.username == chat and user.username in userlist:
                response = {"type": "statusUpdate", "user": client.username, "status": False}
                user.conn.send((json.dumps(response) + "\x04").encode())
    print(f"Server > {client.username} has disconnected.")
    client.conn.close()
    clientList.remove(client)
    del(client)

def sendMessage(message):
    if message["recipient"] != "":
        if accountDb.checkUsername(message["recipient"]) == True:
            if messageDb.checkTable(message["sender"], message["recipient"]) == False:
                messageDb.addTable(message["sender"], message["recipient"])
            for recipient in clientList:
                if recipient.username == message["recipient"]:
                    receiver=recipient.username
                    try:
                        recipient.conn.send(('{"type":"message","sender":"' + message["sender"] + '","message":"' + message["message"] + '"}\x04').encode())
                        messageDb.addMessage(message["sender"], receiver, message["message"])
                        return True
                    except:
                        closeConnection(recipient)
            message["sender"] = message["sender"]
            messageDb.addMessage(message["sender"], message["recipient"], message["message"], 0)
        else:
            print(f"Can't send message to {message['recipient']}. Account doesn't exist.")
        return False


def clientThread(client):
    userlist = getConnectedList()
    for chat in messageDb.getChatsOfUser(client.username):
        chat = chat.split("_")
        if chat[0] == client.username:
            chat = chat[1]
        else:
            chat = chat[0]
        for user in clientList:
            if user.username == chat and user.username in userlist:
                response = {"type": "statusUpdate", "user": client.username, "status": True}
                user.conn.send((json.dumps(response) + "\x04").encode())
                response["user"] = user.username
                client.conn.send((json.dumps(response) + "\x04").encode())
    for message in messageDb.getUnsentMessages(client.username):
        msg = {"sender": message[0], "recipient": client.username, "message": message[1]}
        if sendMessage(msg) == True:
            messageDb.markAsSent(message[3], message[2])
    while True:
        try:
            messages = client.conn.recv(999999).split(b"\x04")
            messages.pop(-1)
            print(messages)
        except Exception as e:
            print(e)
            closeConnection(client)
            break
        for message in messages:
            message = json.loads(message.decode())
            if message["type"] == "message":
                message["sender"] = client.username
                sendMessage(message)
            elif message["type"] == "disconnect":
                closeConnection(client)
                return
            elif message["type"] == "request":
                if message["requestType"] == "status":
                    connectedList = getConnectedList()
                    response = {"type":"requestAnswer", "answerType": "status", "status":[]}
                    for user in connectedList:
                        if user in message["users"]:
                            response["status"].append(user)
                    print(response)
                    client.conn.send((json.dumps(response) + "\x04").encode())
                elif message["requestType"] == "getMessages":
                    output = []
                    for usr in message["list"]:
                        if messageDb.countMessages(client.username, usr[0]) > usr[1]:
                            output.append(messageDb.loadMessages(client.username, usr[0], usr[1]))
                elif message["requestType"] == "deleteChat":
                    messageDb.deleteTable(client.username, message["username"])
        else:
            continue

while True:
    conn, addr = s.accept()
    messages = conn.recv(2048).split(b"\x04")
    messages.pop(-1)
    for message in messages:
        print(message)
        message = json.loads(message.decode("utf-8"))
        if message["type"] == "register": # return if account could be created. Client closes connection.
            account = accountDb.addAccount(message["username"], message["password"])
            if account["success"] == True:
                conn.send((json.dumps({"success": True}) + "\x04").encode())
                print(f"Account for {message['username']} was created")
            else:
                conn.send((json.dumps({"success": False, "error": account["error"]}) + "\x04").encode())
                print(f"Account creation for {message['username']} failed.")
            conn.close()
        elif message["type"] == "loginCheck": # return if data is correct or not.
            if accountDb.checkPassword(message["username"], message["password"]) == True:
                conn.send((json.dumps({"type":"status", "success": True}) + "\x04").encode())
                chats = messageDb.getChatsOfUser(message["username"])
                for chat in chats:
                    chat = chat.split("_")
                    msgs = messageDb.loadMessages(chat[0], chat[1], 1)
                    name = chat[0]
                    if chat[0] == message["username"]:
                        name = chat[1]
                    for msg in msgs:
                        print(msg)
                        conn.send((json.dumps({"type":"message", "user": name, "sender": msg[1], "message": msg[2]}) + "\x04").encode())
                conn.send((json.dumps({"type":"info", "end": True}) + "\x04").encode())
            else:
                conn.send((json.dumps({"type":"status", "success": False, "error": "invalidPassword"}) + "\x04").encode())
            conn.close()
        elif message["type"] == "login":   
            if accountDb.checkPassword(message["username"], message["password"]) == True:
                clientList.append(user(message["username"], conn, addr))
                print(f"Server > {message['username']} has connected. {addr}")
                thread = threading.Thread(target=lambda x=clientList[-1]: clientThread(x))
                thread.start()