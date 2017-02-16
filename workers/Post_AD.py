import __init__
from configparser import ConfigParser
import json
import LocalBitcoin
import ScrapeAds

parser = ConfigParser()
parser.read('../Config.ini')

with open('../Messages.json') as data_file:
    messages = json.load(data_file)

url_buy_ads = "https://localbitcoins.com/buy-bitcoins-online/rub/qiwi/"
url_sell_ads = "https://localbitcoins.com/sell-bitcoins-online/rub/qiwi/"


def edit_ad(lc, ad_ID, price, trade_type, message):
    response = lc.editAd(ad_ID, price, trade_type, message)
    if "data" in response:
        print(response["data"]["message"])
    elif "error" in response:
        print(response["error"]["message"])


def post_ad(lc, price, trade_type, message):
    response = lc.createAd(price, trade_type, message)
    if "data" in response:
        print(response["data"]["message"])
        print("Successful posted AD( "
              + str(response["data"]["ad_id"])
              + ") with price(" + str(price) + ")")
    elif "error" in response:
        print(response["error"]["message"])


def get_price(status, url, username, trade_type):
    ads = ScrapeAds.getAds(url, trade_type)
    print("--------------------------")
    print("First 2 prices:")
    print(str(ads[0].user) + " - " + str(ads[0].price))
    print(str(ads[1].user) + " - " + str(ads[1].price))

    price = False

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


def check_ad(response, index, trade_type):
    if response['data']['ad_list'][index]['data']['trade_type'] == trade_type:
        return True

    return False


def get_status(lc, trade_type):
    response = lc.getOwnAds()
    if int(response['data']['ad_count']) == 1:
        if check_ad(response, 0, trade_type):
            ad_ID = str(response['data']['ad_list'][0]['data']['ad_id'])
            return True, ad_ID
        else:
            return False

    elif int(response['data']['ad_count']) == 2:
        if check_ad(response, 0, trade_type):
            ad_ID = str(response['data']['ad_list'][0]['data']['ad_id'])
            return True, ad_ID
        elif check_ad(response, 1, trade_type):
            ad_ID = str(response['data']['ad_list'][1]['data']['ad_id'])
            return True, ad_ID
        else:
            return False

    elif int(response['data']['ad_count']) == 0:
        return False


def main():
    global parser

    username = parser.get('LocalBitcoins', 'Username')

    # create lc instance
    lc = LocalBitcoin.LocalBitcoin(parser.get('LocalBitcoins', 'Key'), parser.get('LocalBitcoins', 'Secret'))

    ad_type = str(input("Select (sell/buy) type: "))

    # select type
    if ad_type == "sell":
        trade_type = "ONLINE_SELL"
        url = url_buy_ads
        message = messages["sell_msg"]
    elif ad_type == "buy":
        trade_type = "ONLINE_BUY"
        url = url_sell_ads
        message = messages["buy_msg"]
    else:
        print("Incorrect type!!!")
        exit()

    mode = str(input("Select (auto/man) mode: "))

    # select mode
    if mode == "man":
        limit_price = 0
        price = float(input("Select price: "))
        print("--------------------------")
        print("Selected price: " + str(price))
    elif mode == "auto":
        limit_price = float(input("Select limit-price: "))
    else:
        print("Incorrect mode!!!")
        exit()

    while True:
        # get if ad was posted or not
        status = get_status(lc, trade_type)

        # get new price for auto-mode
        if mode == "auto":
            price = get_price(status, url, username, trade_type)

        # check if your price is < than limited one
        if price < limit_price:
            print("\nPrice(" + str(price) +
                  ") is less than limit-price(" + str(limit_price) + ")")
            price = limit_price

        parser.set('Bot', 'SellExchangeRate', str(price))

        if status is False:
                # post new AD
                print("Posting AD...")
                with open('../Config.ini', 'w') as configfile:
                    parser.write(configfile)
                post_ad(lc, price, trade_type, message)
        elif status[0] is True:
                # edit AD
                ad = lc.getAd(status[1])
                old_price = ad["data"]["ad_list"][0]["data"]["price_equation"]
                if float(old_price) != price:
                    print("\nChanging AD's price from(" + str(old_price)
                          + ") to (" + str(price) + ")")
                    with open('../Config.ini', 'w') as configfile:
                        parser.write(configfile)
                    edit_ad(lc, status[1], price, trade_type, message)

        if mode == "man":
            exit()

if __name__ == '__main__':
    main()
