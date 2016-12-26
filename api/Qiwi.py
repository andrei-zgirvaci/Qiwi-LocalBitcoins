import requests
from bs4 import BeautifulSoup
import json

import time


def login(mylogin, mypassword):
    s = requests.Session()
    header = {'content-type': 'application/json', 'X-Requested-With': 'XMLHttpRequest',
              'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:40.0) Gecko/20100101 Firefox/40.0'}

    s.headers = header

    r = s.post('https://auth.qiwi.com/cas/tgts', json={'login': mylogin, 'password': mypassword})

    resp = json.loads(r.text)
    tgtTicket = resp['entity']['ticket']
    r = s.post('https://auth.qiwi.com/cas/sts',
               json={'ticket': tgtTicket, 'service': 'https://qiwi.com/j_spring_cas_security_check'})

    resp = json.loads(r.text)
    stTicket = resp['entity']['ticket']
    r = s.get('https://qiwi.com/j_spring_cas_security_check', params={'ticket': stTicket})

    r = s.get('https://auth.qiwi.com/app/proxy', params={'v': '1'})

    return s


def getLastTransactionAmount(session):
    r = session.post("https://qiwi.com/user/report/list.action", data={'type': '1'})
    soup = BeautifulSoup(r.text,  "html.parser")
    try:
        lastTransaction = soup.findAll("div", {"class": "status_SUCCESS"})[0]
        amount = lastTransaction.findAll("div", {"class": "cash"})[0]
        amount = amount.text.strip().split(" ", 1)[0].replace(",", ".")
    except:
        amount = 0

    return amount


def now_milliseconds():
    return int(time.time() * 1000)


def createTransaction(session, sendTo, amount):
    session.headers['Referer'] = 'https://qiwi.com/payment/form.action?provider=99'
    session.headers['Content-Length'] = '183'
    session.headers['Host'] = 'qiwi.com'
    session.headers['Accept'] = 'application/vnd.qiwi.v2+json'
    # session.headers['']= ''

    session.cookies['TestForThirdPartyCookie'] = 'yes'
    session.cookies['ref'] = 'newsite_b1'
    session.cookies['sms-alert'] = 'none'
    postjson = json.loads('{"id":"","sum":{"amount":"","currency":"643"},"source":"account_643","paymentMethod":{"type":"Account","accountId":"643"},"comment":"","fields":{"account":""}}')
    postjson['id'] = str(now_milliseconds())
    postjson['sum']['amount'] = amount
    postjson['fields']['account'] = sendTo
    res = session.post('https://qiwi.com/user/sinap/api/terms/99/validations/proxy.action', json=postjson)

    session.headers['Referer'] = 'https://qiwi.com/payment/form.action?provider=99&state=confirm'
    session.headers['Content-Length'] = '206'
    postjson = json.loads('{"id":"","sum":{"amount":"","currency":"643"},"source":"account_643","paymentMethod":{"type":"Account","accountId":"643"},"comment":"","fields":{"account":"","_meta_pay_partner":""}}')
    postjson['id'] = str(now_milliseconds())
    postjson['sum']['amount'] = amount
    postjson['fields']['account'] = sendTo
    res = session.post('https://qiwi.com/user/sinap/api/terms/99/payments/proxy.action', json=postjson)
    status = json.loads(res.text)['data']['body']['transaction']['state']['code']
    return status
