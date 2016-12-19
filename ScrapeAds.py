import cfscrape
from bs4 import BeautifulSoup


class Ad:
    user = ""
    price = 0


def getUser(soup, index):
    user = soup.findAll("td", {"class": "column-user"})[index]
    user = user.a.string.split(" ", 1)[0]

    return user


def getPrice(soup, index):
    price = soup.findAll("td", {"class": "column-price"})[index]
    price = price.string.strip().split(" ", 1)[0]

    return float(price)


def getFirtsIndex(soup):
    safe = soup.findAll("i", {"class": "fa-thumbs-o-up"})

    return len(safe)


def getAds(url, trade_type):
    scraper = cfscrape.create_scraper()
    page = scraper.get(url).content
    soup = BeautifulSoup(page,  "html.parser")

    ads = []

    firstIndex = 0

    if trade_type == "ONLINE_BUY":
        firstIndex = getFirtsIndex(soup)

    # get first trade
    ad = Ad()
    ad.user = getUser(soup, firstIndex)
    ad.price = getPrice(soup, firstIndex)
    ads.append(ad)

    # get second trade
    ad = Ad()
    ad.user = getUser(soup, firstIndex+1)
    ad.price = getPrice(soup, firstIndex+1)
    ads.append(ad)

    return ads
