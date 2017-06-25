import cfscrape
from bs4 import BeautifulSoup


class Ad:
    user = ""
    price = 0


def get_user(soup, index):
    user = soup.findAll("td", {"class": "column-user"})[index]
    user = user.a.string.split(" ", 1)[0]

    return user


def get_price(soup, index):
    price = soup.findAll("td", {"class": "column-price"})[index]
    price = price.string.strip().split(" ", 1)[0]

    return float(price)


def get_first_index(soup):
    safe = soup.findAll("i", {"class": "fa-thumbs-o-up"})

    return len(safe)


def get_ads(url, trade_type):
    scraper = cfscrape.create_scraper()
    page = scraper.get(url).content
    soup = BeautifulSoup(page,  "html.parser")

    ads = []

    first_index = 0

    if trade_type == "ONLINE_BUY":
        first_index = get_first_index(soup)

    # get first trade
    ad = Ad()
    ad.user = get_user(soup, first_index)
    ad.price = get_price(soup, first_index)
    ads.append(ad)

    # get second trade
    ad = Ad()
    ad.user = get_user(soup, first_index + 1)
    ad.price = get_price(soup, first_index + 1)
    ads.append(ad)

    return ads
