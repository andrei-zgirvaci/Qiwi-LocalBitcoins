import __init__
import pandas as pd
import threading
from time import sleep
from configparser import ConfigParser
import json
import LocalBitcoin
import Qiwi

parser = ConfigParser()
parser.read('../Config.ini')

with open('../Messages.json') as data_file:
    messages = json.load(data_file)

lc = LocalBitcoin.LocalBitcoin(parser.get('LocalBitcoin', 'Key'), parser.get('LocalBitcoin', 'Secret'))
session = Qiwi.login(parser.get('Qiwi', 'Number'), parser.get('Qiwi', 'Password'))

THREAD_INDEX = 0
MAX_THREADS = int(parser.get('Bot', 'BuyMaxThreads'))
threads = [0] * MAX_THREADS


def printResponse(response):
    if "data" in response:
        print(response['data']['message'])
    elif "error" in response:
        print(response['error']['message'])


def getMessageCount(contactID):
    response = lc.getContactMessages(contactID)
    count = response['data']['message_count']

    return count


def checkMessageForChar(char, contactID):
    try:
        response = lc.getContactMessages(contactID)
        count = getMessageCount(contactID)
        message = response['data']['message_list'][count-1]['msg']
        if char in message:
            return True
    except:
        pass

    return False


def confirmOrder(threadID, contactIndex, contactID, sendTo, amount):
    global lc
    global session
    global THREAD_INDEX
    global threads

    time = 0
    sent = False
    oldCount = 0

    # check an hour if money
    while time < 60:
        df0 = pd.read_csv("../data/Buy_Contacts.csv", sep=',')
        if sent is False:
            print()
            sendMessage(contactID, generateMessageToPay(amount, sendTo))
            oldCount = getMessageCount(contactID)
            print()
            sent = True
        if checkMessageForChar('+', contactID) and oldCount < getMessageCount(contactID):
            print(">>>>------Bot(" + str(threadID) + ")------<<<<")
            print("Transaction confirmed, releasing(" + str(contactID) + ")...")
            status = Qiwi.createTransaction(session, sendTo, amount)
            if status == "Accepted":
                response = lc.markContactAsPaid(contactID)
                printResponse(response)
                sendMessage(contactID, messages["thxMsg"])
            print(">>>>------------------<<<<")
            df0.set_value(contactIndex, 'Status', "Done")
            break
        elif checkMessageForChar('-', contactID) and oldCount < getMessageCount(contactID):
            print(">>>>------Bot(" + str(threadID) + ")------<<<<")
            print("User did not agree, cancelling(" + str(contactID) + ")...")
            response = lc.cancelContact(contactID)
            printResponse(response)
            print(">>>>------------------<<<<")
            df0.set_value(contactIndex, 'Status', "Closed")
            break
        else:
            print(">>>>------Bot(" + str(threadID) + ")------<<<<")
            print("Waiting for(" + str(contactID) + ") to responde...")
            print(">>>>------------------<<<<")
        sleep(60)
        time += 1

    # if time passed, set order as canceled
    if time >= 60:
        print(">>>>------Bot(" + str(threadID) + ")------<<<<")
        print("1 hour passed, cancelling(" + str(contactID) + ")...")
        response = lc.cancelContact(contactID)
        printResponse(response)
        print(">>>>------------------<<<<")
        df0.set_value(contactIndex, 'Status', "Closed")

    df0.to_csv('../data/Buy_Contacts.csv', sep=',', index=False, index_label=False)
    THREAD_INDEX -= 1
    threads[threadID - 1] = 0


def findFreeThread():
    global threads

    for i in range(0, len(threads)):
        if threads[i] == 0:
            return i


def createWorker(contactIndex, contactID, sendTo, amount):
    global THREAD_INDEX
    global threads

    threadID = findFreeThread()
    t = threading.Thread(target=confirmOrder,
                         args=(threadID + 1, contactIndex, contactID, sendTo, amount, ))
    t.daemon = True
    THREAD_INDEX += 1
    threads[threadID] = 1
    t.start()


def sendMessage(contactID, message):
    global lc

    response = lc.postMessageToContact(contactID, message)
    printResponse(response)


def generateMessageToPay(amount, qiwiNr):
    message = messages['buyInvoiceMsg'].replace("$amount", str(amount)).replace("$qiwiNr", str(qiwiNr))

    return message


def setCsvStatus(dataSource, file, index, status):
    dataSource.set_value(index, 'Status', status)
    dataSource.to_csv(file, sep=',', index=False, index_label=False)


def getFreeContact(df0):
    contactIDs = df0.ContactID
    SendTo = df0.SendTo
    amounts = df0.Amount
    Status = df0.Status

    for i, (contactID, amount, sendTo, status) in enumerate(zip(contactIDs, amounts, SendTo, Status)):
        if pd.isnull(status):
            print("Got a new contact: " + str(contactID) + ", qiwi(" + str(sendTo) + ") with: " + str(amount))
            return contactID, amount, sendTo, i
    print("No more contacts, waiting for new ones...")

    return False, False, False, False


def insertNewContact(newContactID, amount, sendTo):
    df0 = pd.read_csv("../data/Buy_Contacts.csv", sep=',')
    contactIDs = df0.ContactID

    for i, contactID in enumerate(contactIDs):
        if contactID == newContactID:
            break
        elif i == len(contactIDs) - 1:
            df0.set_value(i + 1, 'ContactID', newContactID)
            df0.set_value(i + 1, 'Amount', amount)
            df0.set_value(i + 1, 'SendTo', sendTo)
            print("New contactID(" + newContactID + ") inserted")
            df0.to_csv('../data/Buy_Contacts.csv', sep=',', index=False, index_label=False)


def getContacts():
    global lc

    result = lc.getDashboard()
    contacts = result['data']['contact_count']

    for index in range(0, contacts):
        trade_type = result['data']['contact_list'][index]['data']['advertisement']['trade_type']
        if trade_type == "ONLINE_BUY":
            contactID = result['data']['contact_list'][index]['data']['contact_id']
            sendTo = result['data']['contact_list'][index]['data']['account_details']['phone_number']
            amount = result['data']['contact_list'][index]['data']['amount']
            if sendTo[1] != '7':
                amount = float(amount)
                amount -= amount * 0.01
                amount = str(amount)
            insertNewContact(str(contactID), amount, str(sendTo))


def main():
    global THREAD_INDEX
    global MAX_THREADS

    while True:
        print("--------------------------")
        print("Saving orders...")
        # save all contacts
        getContacts()
        df0 = pd.read_csv("../data/Buy_Contacts.csv", sep=',')

        # get a free contact
        print("\nGeting new contact...")
        contactID, amount, sendTo, contactIndex = getFreeContact(df0)
        if contactID is not False:
            print("\nLooking for free bots...")
            if THREAD_INDEX < MAX_THREADS:
                print("Found a free bot, working...")
                setCsvStatus(df0, "../data/Buy_Contacts.csv", contactIndex, "Working")
                createWorker(contactIndex, contactID, sendTo, amount)
            else:
                print("No free bots left, waiting for one...")
        sleep(100)


if __name__ == '__main__':
    main()
