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

thread_index = 0
max_threads = int(parser.get('Bot', 'sell_max_threads'))
threads = [0] * max_threads


def print_response(response):
    if "data" in response:
        print(response["data"]["message"])
    elif "error" in response:
        print(response["error"]["message"])


def check_if_money_received(session, amount):
    amount_received = Qiwi.get_last_transaction_amount(session)

    if float(amount) == float(amount_received):
        return True
    else:
        return False


def confirm_order(thread_ID, contact_index, contact_ID, qiwi_index, qiwi_nr, password, amount):
    global lc
    global thread_index
    global threads

    time = 0
    session = Qiwi.login(qiwi_nr, password)

    df0 = pd.read_csv("../data/Sell_Contacts.csv", sep=',')
    df1 = pd.read_csv("../data/Qiwi_Numbers.csv", sep=',')

    # check an hour if money
    while time < 60:
        if check_if_money_received(session, amount):
            print(">>>>------Bot(" + str(thread_ID) + ")------<<<<")
            print("Transaction received, releasing(" + str(contact_ID) + ")...")
            response = lc.contact_release(contact_ID)
            print_response(response)
            send_message(contact_ID, messages["thx_msg"])
            print(">>>>------------------<<<<")
            df0.set_value(contact_index, 'Status', "Done")
            break
        else:
            print(">>>>------Bot(" + str(thread_ID) + ")------<<<<")
            print("Waiting for(" + str(amount) + ")RUB on " + str(qiwi_nr) + "...")
            print(">>>>------------------<<<<")
        sleep(60)
        time += 1

    # if time passed, set order as canceled
    if time >= 60:
        print(">>>>------Bot(" + str(thread_ID) + ")------<<<<")
        print("1 hour passed, cancelling(" + str(contact_ID) + ")...")
        print(">>>>------------------<<<<")
        df0.set_value(contact_index, 'Status', "Closed")

    df0.to_csv('../data/Sell_Contacts.csv', sep=',', index=False, index_label=False)
    df1.set_value(qiwi_index, 'Status', None)
    df1.to_csv('../data/Qiwi_Numbers.csv', sep=',', index=False, index_label=False)
    thread_index -= 1
    threads[thread_ID - 1] = 0


def find_free_thread():
    global threads

    for i in range(0, len(threads)):
        if threads[i] == 0:
            return i


def create_worker(contact_index, contact_ID, qiwi_index, qiwi_nr, password, amount):
    global thread_index
    global threads

    thread_ID = find_free_thread()
    t = threading.Thread(target=confirm_order,
                         args=(thread_ID + 1, contact_index, contact_ID,
                               qiwi_index, qiwi_nr, password, amount,))
    t.daemon = True
    thread_index += 1
    threads[thread_ID] = 1
    t.start()


def send_message(contact_ID, message):
    global lc

    response = lc.post_message_to_contact(contact_ID, message)
    print_response(response)


def generate_message_to_pay(amount, qiwi_nr):
    message = messages["sell_invoice_msg"].replace("$amount", str(amount)).replace("$qiwi_nr", str(qiwi_nr))

    return message


def set_csv_status(data_source, file, index, status):
    data_source.set_value(index, 'Status', status)
    data_source.to_csv(file, sep=',', index=False, index_label=False)


def get_free_qiwi_nr(df1, amount):
    Qiwi_Nr = df1.QiwiNr
    Password = df1.Password
    Status = df1.Status

    for i, (qiwi_nr, password, status) in enumerate(zip(Qiwi_Nr, Password, Status)):
        if pd.isnull(status):
            qiwi_nr = qiwi_nr.replace('`', '')
            session = Qiwi.login(qiwi_nr, password)
            if not check_if_money_received(session, amount):
                print("Got a new qiwi-number: " + str(qiwi_nr))
                return qiwi_nr, password, i
    print("No more qiwi-numbers, waiting for free ones...")

    return False, False, False


def get_free_contact(df0):
    Contact_ID = df0.ContactID
    Amount = df0.Amount
    Status = df0.Status

    for i, (contact_ID, amount, status) in enumerate(zip(Contact_ID, Amount, Status)):
        if pd.isnull(status):
            print("Got a new contact: " + str(contact_ID) + ", with: " + str(amount))
            return contact_ID, amount, i
    print("No more contacts, waiting for new ones...")

    return False, False, False


def insert_new_contact(new_contact_ID, amount):
    df0 = pd.read_csv("../data/Sell_Contacts.csv", sep=',')
    Contact_ID = df0.ContactID

    exchange_rate = parser.get('Bot', 'sell_exchange_rate')

    for i, contact_ID in enumerate(Contact_ID):
        if contact_ID == new_contact_ID:
            break
        elif i == len(Contact_ID) - 1:
            df0.set_value(i + 1, 'ContactID', new_contact_ID)
            df0.set_value(i + 1, 'Amount', amount)
            df0.set_value(i + 1, 'ExchangeRate', exchange_rate)
            print("New contact_ID(" + new_contact_ID + ") inserted")
            df0.to_csv('../data/Sell_Contacts.csv', sep=',', index=False, index_label=False)


def get_contacts():
    global lc

    result = lc.get_dashboard()
    contacts = result['data']['contact_count']

    for index in range(0, contacts):
        trade_type = result['data']['contact_list'][index]['data']['advertisement']['trade_type']
        if trade_type == "ONLINE_SELL":
            contact_ID = result['data']['contact_list'][index]['data']['contact_id']
            amount = result['data']['contact_list'][index]['data']['amount']
            insert_new_contact(str(contact_ID), amount)


def main():
    global thread_index
    global max_threads

    while True:
        print("--------------------------")
        print("Saving orders...")
        # save all contacts
        get_contacts()
        df0 = pd.read_csv("../data/Sell_Contacts.csv", sep=',')
        df1 = pd.read_csv("../data/Qiwi_Numbers.csv", sep=',')

        # get a free contact
        print("\nGeting new contact...")
        contact_ID, amount, contact_index = get_free_contact(df0)
        if contact_ID is not False:
            print("\nLooking for free bots...")
            if thread_index < max_threads:
                print("Found a free bot, working...")
                # get a free qiwi-number
                print("\nGetting new qiwi-number...")
                qiwi_nr, password, qiwi_index = get_free_qiwi_nr(df1, amount)
                if qiwi_nr is not False:
                    set_csv_status(df0, "../data/Sell_Contacts.csv", contact_index, "Working")
                    set_csv_status(df1, "../data/Qiwi_Numbers.csv", qiwi_index, "Taken")
                    print()
                    send_message(contact_ID, generate_message_to_pay(amount, qiwi_nr))
                    print()
                    create_worker(contact_index, contact_ID,
                                  qiwi_index, qiwi_nr, password, amount)
            else:
                print("No free bots left, waiting for one...")
        sleep(100)


if __name__ == '__main__':
    main()
