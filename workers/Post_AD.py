import __init__
from configparser import ConfigParser
import json
import LocalBitcoin
import ScrapeAds

parser = ConfigParser()
parser.read('../Config.ini')

with open('../Messages.json') as data_file:
    messages = json.load(data_file)

urlBuyAds = "https://localbitcoins.com/buy-bitcoins-online/rub/qiwi/"
urlSellAds = "https://localbitcoins.com/sell-bitcoins-online/rub/qiwi/"


def editAd(lc, adID, price, trade_type, message):
    response = lc.editAd(adID, price, trade_type, message)
    if "data" in response:
        print(response["data"]["message"])
    elif "error" in response:
        print(response["error"]["message"])


def postAd(lc, price, trade_type, message):
    response = lc.createAd(price, trade_type, message)
    if "data" in response:
        print(response["data"]["message"])
        print("Successeful posted AD( "
              + str(response["data"]["ad_id"])
              + ") with price(" + str(price) + ")")
    elif "error" in response:
        print(response["error"]["message"])


def getPrice(status, url, username, trade_type):
    ads = ScrapeAds.getAds(url, trade_type)
    print("--------------------------")
    print("First 2 prices:")
    print(str(ads[0].user) + " - " + str(ads[0].price))
    print(str(ads[1].user) + " - " + str(ads[1].price))

    # get first price
    if status is False:
        price = ads[0].price - 10.00
    # check if an ad is already posted and it's first
    elif status[0] is True and ads[0].user == username:
        price = ads[1].price - 10.00
    # check if an ad is already posted
    elif status[0] is True:
        price = ads[0].price - 10.00

    return price


def checkAd(response, index, trade_type):
    if response['data']['ad_list'][index]['data']['trade_type'] == trade_type:
        return True

    return False


def getStatus(lc, trade_type):
    response = lc.getOwnAds()
    if int(response['data']['ad_count']) == 1:
        if checkAd(response, 0, trade_type):
            adID = str(response['data']['ad_list'][0]['data']['ad_id'])
            return True, adID
        else:
            return False
    if int(response['data']['ad_count']) == 2:
        if checkAd(response, 0, trade_type):
            adID = str(response['data']['ad_list'][0]['data']['ad_id'])
            return True, adID
        elif checkAd(response, 1, trade_type):
            adID = str(response['data']['ad_list'][1]['data']['ad_id'])
            return True, adID
        else:
            return False
    elif int(response['data']['ad_count']) == 0:
        return False


def main():
    global parser

    username = parser.get('LocalBitcoin', 'Username')

    # create lc instance
    lc = LocalBitcoin.LocalBitcoin(parser.get('LocalBitcoin', 'Key'), parser.get('LocalBitcoin', 'Secret'))

    adType = str(input("Select (sell/buy) type: "))

    # select type
    if adType == "sell":
        trade_type = "ONLINE_SELL"
        url = urlBuyAds
        message = messages["sellMsg"]
    elif adType == "buy":
        trade_type = "ONLINE_BUY"
        url = urlSellAds
        message = messages["buyMsg"]
    else:
        print("Incorrect type!!!")
        exit()

    mode = str(input("Select (auto/man) mode: "))

    # select mode
    if mode == "man":
        limitPrice = 0
        price = float(input("Select price: "))
        print("--------------------------")
        print("Selected price: " + str(price))
    elif mode == "auto":
        limitPrice = float(input("Select limit-price: "))
    else:
        print("Incorrect mode!!!")
        exit()

    while True:
        # get if ad was posted or not
        status = getStatus(lc, trade_type)

        # get new price for auto-mode
        if mode == "auto":
            price = getPrice(status, url, username, trade_type)

        # check if your price is < than limited one
        if price < limitPrice:
            print("\nPrice(" + str(price) +
                  ") is less than limit-price(" + str(limitPrice) + ")")
            price = limitPrice

        if status is False:
                # post new AD
                print("Posting AD...")
                postAd(lc, price, trade_type, message)
        elif status[0] is True:
                # edit AD
                ad = lc.getAd(status[1])
                oldPrice = ad["data"]["ad_list"][0]["data"]["price_equation"]
                if float(oldPrice) != price:
                    print("\nChanging AD's price from(" + str(oldPrice)
                          + ") to (" + str(price) + ")")
                    editAd(lc, status[1], price, trade_type, message)

        if mode == "man":
            exit()

if __name__ == '__main__':
    main()
