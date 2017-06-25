import __init__
import pandas as pd
import threading
from time import sleep
from configparser import ConfigParser
import json
import LocalBitcoins
import Qiwi

parser = ConfigParser()
parser.read('../Config.ini')

with open('../Messages.json') as data_file:
    messages = json.load(data_file)

lc = LocalBitcoins.LocalBitcoins(parser.get('LocalBitcoins', 'Key'), parser.get('LocalBitcoins', 'Secret'))
session = Qiwi.login(parser.get('Qiwi', 'Number'), parser.get('Qiwi', 'Password'))

thread_index = 0
max_threads = int(parser.get('Bot', 'buy_max_threads'))
threads = [0] * max_threads


def print_response(response):
    if "data" in response:
        print(response['data']['message'])
    elif "error" in response:
        print(response['error']['message'])


def get_message_count(contact_ID):
    response = lc.get_contact_messages(contact_ID)
    count = response['data']['message_count']

    return count


def check_message_for_char(char, contact_ID):
    try:
        response = lc.get_contact_messages(contact_ID)
        count = get_message_count(contact_ID)
        message = response['data']['message_list'][count-1]['msg']
        if char in message:
            return True
    except:
        pass

    return False


def confirm_order(thread_ID, contact_index, contact_ID, send_to, amount):
    global lc
    global session
    global thread_index
    global threads

    time = 0
    sent = False
    old_count = 0

    df0 = pd.read_csv("../data/Buy_Contacts.csv", sep=',')

    # check an hour if money
    while time < 60:
        if sent is False:
            print()
            send_message(contact_ID, generate_message_to_pay(amount, send_to))
            old_count = get_message_count(contact_ID)
            print()
            sent = True
        if check_message_for_char('+', contact_ID) and old_count < get_message_count(contact_ID):
            print(">>>>------Bot(" + str(thread_ID) + ")------<<<<")
            print("Transaction confirmed, releasing(" + str(contact_ID) + ")...")
            status = Qiwi.create_transaction(session, send_to, amount)
            if status == "Accepted":
                response = lc.mark_contact_as_paid(contact_ID)
                print_response(response)
                send_message(contact_ID, messages["thx_msg"])
            print(">>>>------------------<<<<")
            df0.set_value(contact_index, 'Status', "Done")
            break
        elif check_message_for_char('-', contact_ID) and old_count < get_message_count(contact_ID):
            print(">>>>------Bot(" + str(thread_ID) + ")------<<<<")
            print("User did not agree, cancelling(" + str(contact_ID) + ")...")
            response = lc.cancel_contact(contact_ID)
            print_response(response)
            print(">>>>------------------<<<<")
            df0.set_value(contact_index, 'Status', "Closed")
            break
        else:
            print(">>>>------Bot(" + str(thread_ID) + ")------<<<<")
            print("Waiting for(" + str(contact_ID) + ") to responde...")
            print(">>>>------------------<<<<")
        sleep(60)
        time += 1

    # if time passed, set order as canceled
    if time >= 60:
        print(">>>>------Bot(" + str(thread_ID) + ")------<<<<")
        print("1 hour passed, cancelling(" + str(contact_ID) + ")...")
        response = lc.cancel_contact(contact_ID)
        print_response(response)
        print(">>>>------------------<<<<")
        df0.set_value(contact_index, 'Status', "Closed")

    df0.to_csv('../data/Buy_Contacts.csv', sep=',', index=False, index_label=False)
    thread_index -= 1
    threads[thread_ID - 1] = 0


def find_free_thread():
    global threads

    for i in range(0, len(threads)):
        if threads[i] == 0:
            return i


def create_worker(contact_index, contact_ID, send_to, amount):
    global thread_index
    global threads

    thread_ID = find_free_thread()
    t = threading.Thread(target=confirm_order,
                         args=(thread_ID + 1, contact_index, contact_ID, send_to, amount,))
    t.daemon = True
    thread_index += 1
    threads[thread_ID] = 1
    t.start()


def send_message(contact_ID, message):
    global lc

    response = lc.post_message_to_contact(contact_ID, message)
    print_response(response)


def generate_message_to_pay(amount, qiwi_nr):
    message = messages['buy_invoice_msg'].replace("$amount", str(amount)).replace("$qiwi_nr", str(qiwi_nr))

    return message


def set_csv_status(data_source, file, index, status):
    data_source.set_value(index, 'Status', status)
    data_source.to_csv(file, sep=',', index=False, index_label=False)


def get_free_contact(df0):
    Contact_ID = df0.ContactID
    Send_To = df0.SendTo
    Amounts = df0.Amount
    Status = df0.Status

    for i, (contact_ID, amount, send_to, status) in enumerate(zip(Contact_ID, Amounts, Send_To, Status)):
        if pd.isnull(status):
            print("Got a new contact: " + str(contact_ID) + ", qiwi(" + str(send_to) + ") with: " + str(amount))
            return contact_ID, amount, send_to, i
    print("No more contacts, waiting for new ones...")

    return False, False, False, False


def insert_new_contact(new_contact_ID, amount, send_to):
    df0 = pd.read_csv("../data/Buy_Contacts.csv", sep=',')
    Contact_ID = df0.ContactID

    for i, contact_ID in enumerate(Contact_ID):
        if contact_ID == new_contact_ID:
            break
        elif i == len(Contact_ID) - 1:
            df0.set_value(i + 1, 'ContactID', new_contact_ID)
            df0.set_value(i + 1, 'Amount', amount)
            df0.set_value(i + 1, 'SendTo', send_to)
            print("New contact_ID(" + new_contact_ID + ") inserted")
            df0.to_csv('../data/Buy_Contacts.csv', sep=',', index=False, index_label=False)


def get_contacts():
    global lc

    result = lc.get_dashboard()
    contacts = result['data']['contact_count']

    for index in range(0, contacts):
        trade_type = result['data']['contact_list'][index]['data']['advertisement']['trade_type']
        if trade_type == "ONLINE_BUY":
            contact_ID = result['data']['contact_list'][index]['data']['contact_id']
            send_to = result['data']['contact_list'][index]['data']['account_details']['phone_number']
            amount = result['data']['contact_list'][index]['data']['amount']
            if send_to[1] != '7':
                amount = float(amount)
                amount -= amount * 0.01
                amount = str(amount)
            insert_new_contact(str(contact_ID), amount, str(send_to))


def main():
    global thread_index
    global max_threads

    while True:
        print("--------------------------")
        print("Saving orders...")
        # save all contacts
        get_contacts()
        df0 = pd.read_csv("../data/Buy_Contacts.csv", sep=',')

        # get a free contact
        print("\nGetting new contact...")
        contact_ID, amount, send_to, contact_index = get_free_contact(df0)
        if contact_ID is not False:
            print("\nLooking for free bots...")
            if thread_index < max_threads:
                print("Found a free bot, working...")
                set_csv_status(df0, "../data/Buy_Contacts.csv", contact_index, "Working")
                create_worker(contact_index, contact_ID, send_to, amount)
            else:
                print("No free bots left, waiting for one...")
        sleep(100)


if __name__ == '__main__':
    main()
