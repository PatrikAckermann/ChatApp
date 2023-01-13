import time
import tkinter as tk
import socket
import threading
import os
import json
from tkinter import ttk
import langtranslator as lt
from tkinter import messagebox
import sqlite3
import logging
import hashlib
from win10toast_persist import ToastNotifier # For windows notifications: pip install win10toast-persist
import sv_ttk # For better design: pip install sv-ttk

logging.basicConfig(level=logging.DEBUG, filename="data/log.txt", filemode="a+", format="%(asctime)-15s %(levelname)-8s %(message)s")

def loadSettings():
    file = open("data/settings.json", "r")
    settings = json.loads(file.read())
    file.close()
    return settings

def saveSettings(requireRequests, language, username="", password=""):
    if os.path.exists("data/settings.json"):
        settings = loadSettings()
        if username == "":
            username = settings["name"]
        if password == "":
            password = settings["password"]
    file = open("data/settings.json", "w")
    settings = {"name": username, "password": password,"requireRequests": requireRequests, "language": language}
    file.write(json.dumps(settings))
    file.close()

class messageDb:
    def __init__(self):
        try:
            self.conn = sqlite3.connect("data/messages.db", check_same_thread=False)
            self.c = self.conn.cursor()
        except sqlite3.Error as e:
            logging.error(f"Couldn't connect to database:\n{e}")
        
    def createTable(self, username):
        self.c.execute(f"CREATE TABLE IF NOT EXISTS {username}(id INTEGER PRIMARY KEY, sender TEXT, messages TEXT, sent INTEGER)")
        self.conn.commit()
    
    def deleteTable(self, username):
        self.c.execute(f"DROP TABLE IF EXISTS {username}")
        self.conn.commit()
    
    def getMessageIds(self, userList):
        output = []
        for user in userList:
            self.c.execute(f"SELECT * FROM {user}")
            results = self.c.fetchall()
            output.append([user, len(results)])
        return output

    def getChat(self, username):
        output = []
        self.c.execute(f"SELECT * FROM {username}")
        results = self.c.fetchall()
        for result in results:
            output.append([result[0], result[1], result[2]])
        return output
    
    def saveMessage(self, username, sender, message, sent=1):
        self.c.execute(f"INSERT INTO {username}(sender, messages, sent) VALUES(?, ?, ?)", (sender, message, sent))
        self.conn.commit()
    
    def getUnsentMessages(self, userList):
        output = []
        for recipient in userList:
            self.c.execute(f"SELECT id, sender, messages FROM {recipient} WHERE sent = 0")
            results = self.c.fetchall()
            for result in results:
                output.append([result[1], result[2], result[0]])
        return output
    
    def markAsSent(self, user, id):
        self.c.execute(f"UPDATE {user} SET sent=1 WHERE id=?", (id,))
        self.conn.commit()

class setupWindow:
    def __init__(self):
        self.db = messageDb()

        def closeSetup():
            chatList = []
            #try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.connect(("127.0.0.1", 5432))
            message = {}
            if self.optionVar.get() == "register":
                message = {"type": "register", "username": self.nameEntry.get(), "password": self.passwordEntry.get()}
            elif self.optionVar.get() == "login":
                message = {"type": "loginCheck", "username": self.nameEntry.get(), "password": self.passwordEntry.get()}
            message["password"] = hashlib.sha3_256(message["password"].encode()).hexdigest()
            self.server.send((json.dumps(message) + "\x04").encode())
            stop = False
            while stop == False:
                response = self.server.recv(999999).decode("utf-8").split("\x04")
                response.pop(-1)
                for msg in response:
                    logging.info(msg)
                    msg = json.loads(msg)
                    if self.optionVar.get() == "register":
                        if msg["success"] == False:
                            messagebox.showinfo(message=self.translator.get(msg["error"]))
                            self.server.close()
                            logging.info(f"Account couldn't be created:\n{msg['error']}")
                            return
                        else:
                            logging.info("Account created")
                            stop = True
                    if self.optionVar.get() == "login":
                        if msg["type"] == "status":
                            if msg["success"] == False:
                                messagebox.showinfo(message=self.translator.get(msg["error"]))
                                self.server.close()
                                logging.info("No success")
                                return
                            else:
                                logging.info("Success")
                        elif msg["type"] == "message":
                            if msg["user"] not in chatList:
                                chatList.append(msg["user"])
                            self.db.createTable(msg["user"])
                            self.db.saveMessage(msg["user"], msg["sender"], msg["message"])
                        elif msg["type"] == "info":
                            if msg["end"] == True:
                                stop = True
            self.server.close()
            convertedChatlist = []
            if self.optionVar.get() == "login":
                for usr in chatList:
                    convertedChatlist.append([usr, True])
            file = open("data/chatList.json", "w")
            file.write(json.dumps(convertedChatlist))
            file.close()
            self.db.conn.close()
            saveSettings(False, self.convertedLanguage, self.nameEntry.get(), hashlib.sha3_256(self.passwordEntry.get().encode()).hexdigest())
            self.window.destroy()
        
        # Language settings

        self.window = tk.Tk()
        self.language = tk.StringVar()

        def chooseLanguage():
            self.convertedLanguage = ""
            if self.language.get() == "English":
                self.convertedLanguage = "en"
            else:
                self.convertedLanguage = "de"
            self.window.destroy()

        options = ["Deutsch", "English"]
        languageSelector = tk.OptionMenu(self.window, self.language, *options)
        self.language.set("English")
        languageSelector.grid(row=0, column=0)
        confirmButton = tk.Button(self.window, text="✔️", command=chooseLanguage)
        confirmButton.grid(row=0, column=1)
        self.window.mainloop()

        # Register/login
        self.translator = lt.langtranslator("data/translations.json", self.convertedLanguage)

        self.window = tk.Tk()

        self.optionVar = tk.StringVar()
        self.optionVar.set("register")
        registerButton = tk.Radiobutton(self.window, text=self.translator.get("register"), value="register", variable=self.optionVar)
        loginButton = tk.Radiobutton(self.window, text=self.translator.get("login"), value="login", variable=self.optionVar)
        nameLabel = tk.Label(text=self.translator.get("name"))
        self.nameEntry = tk.Entry()
        passwordLabel = tk.Label(text=self.translator.get("password"))
        self.passwordEntry = tk.Entry()
        confirmButton = tk.Button(text=self.translator.get("confirm"), command=closeSetup)

        registerButton.grid(row=0, column=0)
        loginButton.grid(row=0, column=1)
        nameLabel.grid(row=1, column=0)
        self.nameEntry.grid(row=1, column=1)
        passwordLabel.grid(row=2, column=0)
        self.passwordEntry.grid(row=2, column=1)
        confirmButton.grid(row=3, column=1)

        self.window.mainloop()

class windowClass:
    def __init__(self):
        ##### LOAD SETTINGS AND CONFIGURE WINDOW #####
        self.settings = loadSettings()
        if not isinstance(self.settings["name"], str) or not isinstance(self.settings["requireRequests"], bool):
            self.settingsWindow() # make user redo the settings

        self.translator = lt.langtranslator("data/translations.json", self.settings["language"])
        self.db = messageDb()

        self.serverIp = "127.0.0.1"
        self.serverPort = "5432"
        self.username = self.settings["name"]
        self.password = self.settings["password"]

        self.window = tk.Tk()
        self.window.protocol("WM_DELETE_WINDOW", self.closeWindow)
        sv_ttk.set_theme("dark")

        self.window.rowconfigure(0, weight=1)
        self.window.columnconfigure(1, weight=1)

        self.chatList = [] # List of chat objects
        self.chatRequests = [] # List of users that want to chat with this person.

        self.listFrame = ttk.Frame(self.window)
        chatFrame = ttk.Frame(self.window)

        ##### LISTFRAME CONTENT #####
        btnFrame = tk.Frame(self.listFrame)
        newChatButton = ttk.Button(btnFrame, text=self.translator.get("newChat"), command=self.newChat)
        requestsButton = ttk.Button(btnFrame, text=self.translator.get("chatRequests"), command=self.requestsWindow)
        settingsButton = ttk.Button(self.listFrame, text="⚙", command=self.settingsWindow)
        listCanvas = tk.Canvas(self.listFrame, width=30)
        self.canvasFrame = tk.Frame(listCanvas, width=200)
        listScrollbar = ttk.Scrollbar(self.listFrame, orient="vertical", command=listCanvas.yview)

        listCanvas.columnconfigure(0, weight=1)
        self.listFrame.rowconfigure(1, weight=1)

        btnFrame.grid(row=0, column=0)
        newChatButton.grid(row=0, column=0, sticky="new")
        requestsButton.grid(row=0, column=1, sticky="new", columnspan=2)
        settingsButton.grid(row=0, column=1, sticky="new")
        listCanvas.grid(row=1, column=0, sticky="nsew")
        listScrollbar.grid(row=1, column=1, sticky="nse")

        self.canvasFrame.bind("<Configure>", lambda e: listCanvas.configure(scrollregion=listCanvas.bbox("all")))
        listCanvas.create_window(0, 0, window=self.canvasFrame, anchor="nw")
        listCanvas.configure(yscrollcommand=listScrollbar.set)

        ##### CHATFRAME CONTENT #####
        self.chatHeader = tk.Frame(chatFrame)
        self.nameLabel = ttk.Label(self.chatHeader)
        self.deleteButton = ttk.Button(self.chatHeader, text="🗑️", width=3, command=self.deleteChat)
        self.messages = tk.Text(chatFrame, state="disabled", bg="#1c1c1c", fg="white")
        self.messageEntry = ttk.Entry(chatFrame)
        messageSendButton = ttk.Button(chatFrame, text=self.translator.get("send"), command=self.send)

        chatFrame.columnconfigure(0, weight=1)
        chatFrame.rowconfigure(0, weight=1)

        self.chatHeader.rowconfigure(0, weight=1)
        self.chatHeader.columnconfigure(1, weight=1)

        self.chatHeader.grid(row=0, column=0, sticky="new", columnspan=2)
        self.nameLabel.grid(row=0, column=0, sticky="w", padx=5)
        self.deleteButton.grid(row=0, column=1, sticky="ne")
        self.messages.grid(row=1, column=0, sticky="nsew", columnspan=2)
        self.messageEntry.grid(row=2, column=0, sticky="nsew")
        messageSendButton.grid(row=2, column=1, sticky="es")

        self.listFrame.grid(row=0, column=0, sticky="nsw")
        chatFrame.grid(row=0, column=1, sticky="nsew")

        if os.path.exists("data/chatList.json"):
            userList = self.loadChatList()
            if userList:
                for user in userList:
                    self.addToList(user[0], user[1])
                    if user[1] == False and self.settings["requireRequests"] == True:
                        self.chatRequests.append(user[0])

        self.connThread = threading.Thread(target=self.connectionThread)
        self.connThread.setDaemon(True)
        self.connThread.start()

        self.currentChat = ""

        self.window.bind("<Return>", self.send)

        self.window.mainloop()
    
    def deleteChat(self):
        user = self.currentChat
        if len(self.chatList) >= 2:
            if self.chatList[0].username != user:
                self.changeChat(self.chatList[0].username)
            else:
                self.changeChat(self.chatList[1].username)
        self.db.deleteTable(user)
        for chat in self.chatList:
            if chat.username == user:
                chat.listFrame.grid_forget()
                self.chatList.remove(chat)
        self.saveChatList()
        self.sendToServer({"type": "request", "requestType": "deleteChat", "username": user})

    def changeChat(self, username):
        logging.info(f"Changed chat to {username}")
        self.messages["state"] = "normal"
        self.messages.delete("1.0", tk.END)
        for chat in self.chatList:
            if chat.username == username:
                chat.changeBg("#333333")
                for message in self.db.getChat(username):
                    self.messages.insert(tk.END, f"{message[1]} > {message[2]}\n")
                self.currentChat = username
            else:
                chat.changeBg("#1c1c1c")
        self.messages.see("end")
        self.messages["state"] = "disabled"
        self.nameLabel["text"] = self.currentChat

    def closeWindow(self):
        try:
            self.server.send(b'{"type":"disconnect"}\x04')
        except:
            logging.error("Can't send disconnect")
        self.window.destroy()
        exit()

    def newChat(self):
        def setRecipient():
            if usernameEntry.get().isnumeric() == False and usernameEntry.get().isalnum():
                self.recipient = usernameEntry.get()
                self.addToList(usernameEntry.get(), True)
                newChatWindow.destroy()
            else:
                messagebox.showinfo("Error", "username not allowed(gets replaced with server check if user exists)")

        newChatWindow = tk.Toplevel()
        usernameLabel = ttk.Label(newChatWindow, text=self.translator.get("username"))
        usernameEntry = ttk.Entry(newChatWindow)
        confirmButton = ttk.Button(newChatWindow, text=self.translator.get("confirm"), command=setRecipient)

        usernameLabel.grid(row=0, column=0)
        usernameEntry.grid(row=0, column=1)
        confirmButton.grid(row=1, column=1)

    def send(self, x=""): #x because the enter button press sends an argument
        if self.currentChat != "":
            message = {"type":"message","recipient":self.currentChat,"message":self.messageEntry.get()}
            if self.sendToServer(message) == False:
                self.db.saveMessage(self.currentChat, self.username, self.messageEntry.get(), 0)
            else:
                self.db.saveMessage(self.currentChat, self.username, self.messageEntry.get(), 1)
            self.changeChat(self.currentChat) #Reloads chat so it shows sent message
    
    def sendToServer(self, dict):
        output = False
        try:
            message = (json.dumps(dict) + "\x04").encode() #need to add \x04 to end of message to mark end of message
            self.server.send(message)
            output = True
        except Exception as e:
            logging.error(f"Error > Couldn't send message.\n{e}")
        if dict["type"] == "message":
            self.printMessage(self.username, dict["message"])
        return output
        
    def printMessage(self, name, message):
        for chat in self.chatList or chat.username == self.currentChat and name == self.username:
            if chat.username == name:
                self.db.saveMessage(chat.username, name, message)
                chat.messages.append([name, message])
                break
        
        if self.currentChat == name or name == self.username:
            self.changeChat(self.currentChat)
           
        logging.info(f"Message printed: {name} > {message}")
    
    def sendNotification(self, username, message): # Shows if message is received in list. If window is out of focus it will also send a notification to windows.
        if not self.window.focus_displayof():
            toast = ToastNotifier()
            toast.show_toast(username, message, threaded=True)
        if self.currentChat != username:
            for chat in self.chatList:
                if chat.username == username:
                    chat.changeBg("#ff8080")

    def updateStatus(self, username, online):
        for chat in self.chatList:
            if chat.username == username:
                if online == True:
                    chat.status = True
                    chat.statusLabel["text"] = self.translator.get("online")
                    chat.statusLabel["fg"] = "green"
                else:
                    chat.status = False
                    chat.statusLabel["text"] = self.translator.get("online")
                    chat.statusLabel["fg"] = "red"
    
    def addToList(self, username, requestAccepted=False):
        self.chatList.append(chat(username, "Offline", tk.Frame(self.canvasFrame), requestAccepted))
        self.saveChatList()
        self.db.createTable(username)
        if self.settings["requireRequests"] == True and self.chatList[-1].requestAccepted == False:
            return self.chatList[-1]
        self.showChat(self.chatList[-1])

    def getNames(self):
        output = []
        for chat in self.chatList:
            output.append(chat.username)
        return output
    
    def showChat(self, chatObject):
        chatObject.listFrame.grid(row=len(self.chatList) - len(self.chatRequests), column=0, sticky="NEW")
        for widget in chatObject.listFrame.winfo_children():
            widget.bind("<Button-1>", lambda e, name=chatObject.username: self.changeChat(name)) #e because otherwise the username variable gets replaced by the ButtonPress event
        chatObject.listFrame.bind("<Button-1>", lambda e, name=chatObject.username: self.changeChat(name))
        return chatObject
    
    def getChatObj(self, chatList, user):
        for chat in chatList:
            if chat.username == user:
                return chat
    
    def removeFromList(self, username):
        for chat in self.chatList:
            if chat.username == username:
                chat.listFrame.grid_forget()
                self.chatList.remove(chat)
    
    def saveChatList(self):
        chatList = []
        for chat in self.chatList:
            chatList.append([chat.username, chat.requestAccepted])
        file = open("data/chatList.json", "w")
        file.write(json.dumps(chatList))
        file.close()
    
    def loadChatList(self):
        file = open("data/chatList.json", "r")
        output = json.loads(file.readline())
        file.close()
        return output

    def connectionThread(self):
        while True:
            try:
                self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server.connect(("127.0.0.1", 5432))
            except:
                for chat in self.chatList:
                    self.updateStatus(chat.username, False)
                continue
            self.sendToServer({"type":"login","username":self.username,"password":self.password})
            userlist = []
            for chat in self.chatList:
                userlist.append(chat.username)
            for message in self.db.getUnsentMessages(userlist):
                if self.sendToServer({"type":"message", "recipient":message[0], "message":message[1]}) == True:
                    self.db.markAsSent(message[0], message[2])
            while True:
                try:
                    messages = self.server.recv(999999).split(b"\x04") 
                    messages.pop(-1)
                except Exception as e:
                    logging.error(f"Couldn't receive messages.\n{e}")
                    logging.info("Server offline")
                    break
                for message in messages:
                    message = json.loads(message)
                    if message["type"] == "message":
                        if message["sender"] not in self.getNames():
                            if self.settings["requireRequests"] == False:
                                self.addToList(message["sender"], True)
                            else:
                                chatObj = self.addToList(message["sender"], False)
                                self.chatRequests.append(message["sender"])
                                chatObj.messages.append([message["sender"], message["message"]])
                        if self.settings["requireRequests"] == True and self.getChatObj(self.chatList, message["sender"]).requestAccepted == False:
                            self.db.createTable(message["sender"])
                            self.db.saveMessage(message["sender"], message["sender"], message["message"])
                            continue
                        self.printMessage(message["sender"], message["message"])     
                        self.sendNotification(message["sender"], message["message"])  
                    elif message["type"] == "messageList":
                        for msg in message["messages"]:
                            if msg["sender"] not in self.getNames():
                                self.addToList(msg["sender"])
                    elif message["type"] == "statusUpdate":
                        self.updateStatus(message["user"], message["status"])
                    else:
                        logging.error("Received a message with unsupported type. Client could be outdated.")
            time.sleep(5)
    
    def settingsWindow(self):
        def saveAndClose():
            if language.get() == "English":
                lang = "en"
            else:
                lang = "de"
            saveSettings(requests.get(), lang)
            settingsWindow.destroy()
        
        def logout():
            self.db.conn.close()
            os.remove("data\\settings.json")
            os.remove("data\\messages.db")
            os.remove("data\\chatList.json")
            exit()
        
        settingsWindow = tk.Toplevel()
        requests = tk.BooleanVar()
        requests.set(False)
        language = tk.StringVar()
        language.set("English")
        languageOptions = ["English", "Deutsch"]
        requestsLabel = ttk.Label(settingsWindow, text=self.translator.get("requests"))
        requestFrame = ttk.Frame(settingsWindow)
        requestFalse = ttk.Radiobutton(requestFrame, variable=requests, value=False, text=self.translator.get("no"))
        requestTrue = ttk.Radiobutton(requestFrame, variable=requests, value=True, text=self.translator.get("yes"))
        separator1 = ttk.Separator(settingsWindow)
        languageLabel = ttk.Label(settingsWindow, text=self.translator.get("language"))
        languageDropdown = ttk.OptionMenu(settingsWindow, language, languageOptions[0], *languageOptions)
        separator2 = ttk.Separator(settingsWindow)
        confirmButton = ttk.Button(settingsWindow, text=self.translator.get("confirm"), command=saveAndClose)
        logoutButton = ttk.Button(settingsWindow, text=self.translator.get("logout"), command=logout)

        requestsLabel.grid(row=0, column=0)
        requestFrame.grid(row=0, column=1)
        requestFalse.grid(row=0, column=1)
        requestTrue.grid(row=0, column=2)
        separator1.grid(row=1, column=0, columnspan=2, sticky="ew")
        languageLabel.grid(row=3, column=0)
        languageDropdown.grid(row=3, column=1, pady=3)
        separator2.grid(row=5, column=0, columnspan=2, sticky="ew")
        confirmButton.grid(row=10, column=1, pady=3)
        logoutButton.grid(row=10, column=0, pady=3)
    
    def requestsWindow(self):
        def loadNewRequest():
            if self.chatRequests != []:
                acceptButton["state"] = "normal"
                declineButton["state"] = "normal"
                nameLabel["text"] = self.chatRequests[0]
            else:
                acceptButton["state"] = "disabled"
                declineButton["state"] = "disabled"
                nameLabel["text"] = self.translator.get("noRequests")
        def acceptRequest():
            for chatObj in self.chatList:
                if chatObj.username == self.chatRequests[0]:
                    chatObj.requestAccepted = True
                    self.showChat(chatObj)
                    break
            self.chatRequests.pop(0)
            loadNewRequest()
        def declineRequest():
            self.chatRequests.pop(0)
            loadNewRequest()

        requestsWindow = tk.Toplevel()
        nameLabel = ttk.Label(requestsWindow, text=self.translator.get("noRequests"))
        acceptButton = ttk.Button(requestsWindow, text=self.translator.get("accept"), command=acceptRequest)
        declineButton = ttk.Button(requestsWindow, text=self.translator.get("decline"), command=declineRequest)

        loadNewRequest()

        nameLabel.grid(row=0, column=0, columnspan=2)
        acceptButton.grid(row=1, column=0)
        declineButton.grid(row=1, column=1)


class chat:
    def __init__(self, username, status, listFrame, requestAccepted=True):
        self.username = username
        self.status = status
        self.listFrame = listFrame
        self.messages = [] #Format: ["sender", "message"]
        self.requestAccepted = requestAccepted

        self.nameLabel = tk.Label(self.listFrame, text=self.username, width=37, anchor="w")
        self.nameLabel.grid(row=0, column=0)
        self.statusLabel = tk.Label(self.listFrame, text=self.status, fg="red", width=37, anchor="w")
        self.statusLabel.grid(row=1, column=0)
        self.spacer = ttk.Separator(listFrame)
        self.spacer.grid(row=2, column=0, sticky="ew")
    
    def changeBg(self, color):
        self.listFrame["bg"] = self.nameLabel["bg"] = self.statusLabel["bg"] = color


if not os.path.exists("data/settings.json"):
    appSetup = setupWindow()
window = windowClass()