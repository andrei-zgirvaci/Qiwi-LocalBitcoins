import LocalBitcoin
import Qiwi
import pandas as pd
import threading
from time import sleep
from configparser import ConfigParser
import json

parser = ConfigParser()
parser.read('config.ini')

with open('messages.json') as data_file:
    messages = json.load(data_file)

lc = LocalBitcoin.LocalBitcoin(parser.get('LocalBitcoin', 'Key'), parser.get('LocalBitcoin', 'Secret'))

THREAD_INDEX = 0
MAX_THREADS = int(parser.get('Bot', 'SellMaxThreads'))
threads = [0] * MAX_THREADS


def printResponse(response):
    if "data" in response:
        print(response["data"]["message"])
    elif "error" in response:
        print(response["error"]["message"])


def checkIfMoneyRecieved(session, amount):
    amountRecieved = Qiwi.getLastTransactionAmount(session)

    if float(amount) == float(amountRecieved):
        return True
    else:
        return False


def confirmOrder(threadID, contactIndex, contactID, qiwiIndex, qiwiNr, password, amount):
    global lc
    global THREAD_INDEX
    global threads

    time = 0
    session = Qiwi.login(qiwiNr, password)

    # check an hour if money
    while time < 60:
        df0 = pd.read_csv("Sell_Contacts.csv", sep=',')
        df1 = pd.read_csv("Qiwi.csv", sep=',')
        if checkIfMoneyRecieved(session, amount):
            print(">>>>------Bot(" + str(threadID) + ")------<<<<")
            print("Transaction recieved, releasing(" + str(contactID) + ")...")
            response = lc.contactRelease(contactID)
            printResponse(response)
            sendMessage(contactID, messages["thxMsg"])
            print(">>>>------------------<<<<")
            df0.set_value(contactIndex, 'Status', "Done")
            break
        else:
            print(">>>>------Bot(" + str(threadID) + ")------<<<<")
            print("Waiting for(" + str(amount) + ")RUB on " + str(qiwiNr) + "...")
            print(">>>>------------------<<<<")
        sleep(60)
        time += 1

    # if time passed, set order as canceled
    if time >= 60:
        print(">>>>------Bot(" + str(threadID) + ")------<<<<")
        print("1 hour passed, cancelling(" + str(contactID) + ")...")
        print(">>>>------------------<<<<")
        df0.set_value(contactIndex, 'Status', "Closed")

    df0.to_csv('Sell_Contacts.csv', sep=',', index=False, index_label=False)
    df1.set_value(qiwiIndex, 'Status', None)
    df1.to_csv('Qiwi.csv', sep=',', index=False, index_label=False)
    THREAD_INDEX -= 1
    threads[threadID - 1] = 0


def findFreeThread():
    global threads

    for i in range(0, len(threads)):
        if threads[i] == 0:
            return i


def createWorker(contactIndex, contactID, qiwiIndex, qiwiNr, password, amount):
    global THREAD_INDEX
    global threads

    threadID = findFreeThread()
    t = threading.Thread(target=confirmOrder,
                         args=(threadID + 1, contactIndex, contactID,
                               qiwiIndex, qiwiNr, password, amount, ))
    t.daemon = True
    THREAD_INDEX += 1
    threads[threadID] = 1
    t.start()


def sendMessage(contactID, message):
    global lc

    response = lc.postMessageToContact(contactID, message)
    printResponse(response)


def generateMessageToPay(amount, qiwiNr):
    message = messages["sellInvoiceMsg"].replace("$amount", str(amount)).replace("$qiwiNr",  str(qiwiNr))

    return message


def setCsvStatus(dataSource, file, index, status):
    dataSource.set_value(index, 'Status', status)
    dataSource.to_csv(file, sep=',', index=False, index_label=False)


def getFreeQiwiNr(df1, amount):
    qiwiNrs = df1.QiwiNr
    passwords = df1.Password
    Status = df1.Status

    for i, (qiwiNr, password, status) in enumerate(zip(qiwiNrs, passwords, Status)):
        if pd.isnull(status):
            qiwiNr = qiwiNr.replace('`', '')
            session = Qiwi.login(qiwiNr, password)
            if not checkIfMoneyRecieved(session, amount):
                print("Got a new qiwi-number: " + str(qiwiNr))
                return qiwiNr, password, i
    print("No more qiwi-numbers, waiting for free ones...")

    return False, False, False


def getFreeContact(df0):
    contactIDs = df0.ContactID
    amounts = df0.Amount
    Status = df0.Status

    for i, (contactID, amount, status) in enumerate(zip(contactIDs, amounts, Status)):
        if pd.isnull(status):
            print("Got a new contact: " + str(contactID) + ", with: " + str(amount))
            return contactID, amount, i
    print("No more contacts, waiting for new ones...")

    return False, False, False


def insertNewContact(newContactID, amount):
    df0 = pd.read_csv("Sell_Contacts.csv", sep=',')
    contactIDs = df0.ContactID

    for i, contactID in enumerate(contactIDs):
        if contactID == newContactID:
            break
        elif i == len(contactIDs) - 1:
            df0.set_value(i + 1, 'ContactID', newContactID)
            df0.set_value(i + 1, 'Amount', amount)
            print("New contactID(" + newContactID + ") inserted")
            df0.to_csv('Sell_Contacts.csv', sep=',', index=False, index_label=False)


def getContacts():
    global lc

    result = lc.getDashboard()
    contacts = result['data']['contact_count']

    for index in range(0, contacts):
        trade_type = result['data']['contact_list'][index]['data']['advertisement']['trade_type']
        if trade_type == "ONLINE_SELL":
            contactID = result['data']['contact_list'][index]['data']['contact_id']
            amount = result['data']['contact_list'][index]['data']['amount']
            insertNewContact(str(contactID), amount)


def main():
    global THREAD_INDEX
    global MAX_THREADS

    while True:
        print("--------------------------")
        print("Saving orders...")
        # save all contacts
        getContacts()
        df0 = pd.read_csv("Sell_Contacts.csv", sep=',')
        df1 = pd.read_csv("Qiwi.csv", sep=',')

        # get a free contact
        print("\nGeting new contact...")
        contactID, amount, contactIndex = getFreeContact(df0)
        if contactID is not False:
            print("\nLooking for free bots...")
            if THREAD_INDEX < MAX_THREADS:
                print("Found a free bot, working...")
                # get a free qiwi-number
                print("\nGeting new qiwi-number...")
                qiwiNr, password, qiwiIndex = getFreeQiwiNr(df1, amount)
                if qiwiNr is not False:
                    setCsvStatus(df0, "Sell_Contacts.csv", contactIndex, "Working")
                    setCsvStatus(df1, "Qiwi.csv", qiwiIndex, "Taken")
                    print()
                    sendMessage(contactID, generateMessageToPay(amount, qiwiNr))
                    print()
                    createWorker(contactIndex, contactID,
                                 qiwiIndex, qiwiNr, password, amount)
            else:
                print("No free bots left, waiting for one...")
        sleep(100)


if __name__ == '__main__':
    main()
