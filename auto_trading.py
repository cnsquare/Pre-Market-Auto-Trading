import argparse
import getpass
import urllib
import urllib.request
import re
import schedule
import time
import sys
import datetime
import requests
import csv
import os

from Robinhood import Robinhood

logged_in = False

# hard code your credentials here to avoid entering them each time you run the script
username = ""
password = ""

parser = argparse.ArgumentParser(description='Export Robinhood trades to a CSV file')
parser.add_argument('--debug', action='store_true', help='store raw JSON output to debug.json')
parser.add_argument('--username', default=username, help='your Robinhood username')
parser.add_argument('--password', default=password, help='your Robinhood password')
args = parser.parse_args()
username = args.username
password = args.password

robinhood = Robinhood()

sell_stock = []
num_sell_stock = []
buydate = ""
selldate = ""
beforecash = 0
investedcash = 0
earnings = 0


def auto_trade():
    print(datetime.datetime.now())
    print("Starting to run...\n")


    # Buy today's positions
    set_time = "18:22"
    schedule.every().monday.at(set_time).do(run)
    schedule.every().tuesday.at(set_time).do(run)
    schedule.every().wednesday.at(set_time).do(run)
    schedule.every().thursday.at(set_time).do(run)
    schedule.every().friday.at(set_time).do(run)

    # Sell yesterday's positions
    set_time = "16:34"
    schedule.every().monday.at(set_time).do(sellme)
    schedule.every().tuesday.at(set_time).do(sellme)
    schedule.every().wednesday.at(set_time).do(sellme)
    schedule.every().thursday.at(set_time).do(sellme)
    schedule.every().friday.at(set_time).do(sellme)

    while True:
        schedule.run_pending()
        sys.stdout.flush()
        time.sleep(1)  # Check every 1 second


def run():
    print("running")
    raw_data = data_mining("http://www.thestockmarketwatch.com/markets/pre-market/today.aspx")
    clean_s, clean_p, clean_v = data_cleanup(raw_data)
    selected_s, selected_p, selected_v = data_refinement(clean_s, clean_p, clean_v)
    stock, num_stocks = pre_purchase_cal(selected_s, selected_p)
    buy(stock, num_stocks)
    global sell_stock, num_sell_stock
    sell_stock, num_sell_stock = stock, num_stocks
    sellme()


def data_mining(base):
    # Only stockmarketwatch
    print("Accessing webpage")
    print("")
    print("Retriving raw data from " + base)
    print("")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/56.0.2924.51 Safari/537.36'}
    try:
        response = requests.get(base, headers=headers)
        text = response.content.decode()
    except urllib.error.HTTPError:
        print("Error loading page")
        return []
    return text


def data_cleanup(text):
    # Get list of gainer symbols
    reg_ex = 'symbol\" href=\"/stock/\?stock=(.+?)\"'
    gainers = re.findall(reg_ex, text, re.M)[:15]
    # pprint(gainers)

    # Get list of gainer prices
    reg_ex = 'div class=\"lastPrice\"\>([0-9].+?)\<'
    prices = re.findall(reg_ex, text, re.M)[:15]

    # Get list of gainer volumes
    reg_ex = 'class=\"volume2\">([0-9].*?)\<'
    volumes = re.findall(reg_ex, text, re.M)[:15]

    return gainers, prices, volumes


def data_refinement(gainers, prices, volumes):
    for i in (gainers, prices, volumes):
        print(i)

    # Filter gainer list by cutoff price and volume
    results_price = []
    results_stock = []
    results_volume = []
    n = 0
    for stock in gainers:
        if float(prices[n]) < 80:  # Cutoff price
            if float(volumes[n]) > 8000:  # At least this volume
                results_stock.append(stock)
                results_price.append(float(prices[n]))
                results_volume.append(float(volumes[n]))
        n += 1
    print("\nSelected Stocks based on price and volume")
    for i in results_stock:
        print(i)
    print("")
    # pdb.set_trace()
    return results_stock, results_price, results_volume


def pre_purchase_cal(final_stock, final_price):
    global beforecash
    local_account = [0] * len(final_stock)

    f = open("bank.txt", "r")
    my_equity = float(f.read().__str__())
    beforecash = my_equity

    n = 0
    while float(my_equity) > float(min(final_price)):
        #print(float(my_equity), float(min(final_price)), "Main")
        for cash in final_price:
            if (float(my_equity) - float(cash)) > 0:
                # print(float(my_equity), float(cash), "Sub")
                my_equity = float(my_equity) - float(cash)
                local_account[n] = (local_account[n] + 1)
            n += 1
        n = 0

    n = 0
    for i in final_stock:
        print("Will buy " + local_account[n].__str__() + " stock(s) of " + i + " for approximately " + final_price[
            n].__str__()
              + " each for a Total of " + (float(final_price[n]) * int(local_account[n])).__str__())
        n += 1
    print("")
    print("Remaining Equity : " + my_equity.__str__())
    global remaining
    remaining = my_equity
    # pdb.set_trace()
    return final_stock, local_account


def buy(stock, num_stock):
    global investedcash
    global buydate
    total_cost = 0
    i = 0
    print("")
    for item in stock:
        # print("Buying......" + num_stock[i].__str__() + " stock(s) of " + item)
        # robinhood.place_buy_order(stock,num_stock,bid_price=None)
        print("Robinhood completed buy of " + int(num_stock[i]).__str__() + " " + item + " at " +
              robinhood.bid_price(item) + " per stock...Total " + (float(robinhood.bid_price(item)) *
                                                                   (int(num_stock[i]))).__str__())
        total_cost += (float(robinhood.bid_price(item)) * int(num_stock[i]))
        i += 1
    investedcash = total_cost
    print("\nTotal amount spent : " + total_cost.__str__())
    print("Purchase Complete ")

    buydate = datetime.date.today().isoformat()

    if not os.path.exists('metrics.csv'):
        csv_create()


def sellme():
    sell(sell_stock, num_sell_stock)


def sell(stock, num_stock):
    global selldate
    global earnings
    i = 0
    total_cost = 0
    print("")
    for item in stock:
        print("Selling......" + num_stock[i].__str__() + " stock(s) of " + item)
        total_cost += (float(robinhood.bid_price(item)) * int(num_stock[i]))
        i += 1
    print("Selling Complete ")

    print("testing....................." + float(total_cost + remaining).__str__())


    f = open("bank.txt", "w")
    f.write((float(total_cost + remaining)).__str__())
    f.close()

    selldate = datetime.date.today().isoformat()

    earnings = total_cost
    csv_write(buydate, selldate, beforecash, investedcash, earnings)


def csv_create():
    csv_columns = ['Buy Date', 'Sell Date', 'Beginning Amount', 'Invested Amount', 'Earnings', 'Total']
    with open('metrics.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, dialect='excel', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(csv_columns)
        csvfile.close()


def csv_write(buydate, selldate, beforecash, investedcash, earnings):
    info = [buydate, selldate, beforecash, investedcash, earnings]
    print(info)
    with open('metrics.csv', 'a', newline='') as csvfile:
        writer = csv.writer(csvfile, dialect='excel', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(info)
        csvfile.close()


# login to Robinhood
while not logged_in:
    if username == "":
        print("Robinhood username:")
        try:
            input = raw_input
        except NameError:
            pass
        username = input()
    if password == "":
        password = getpass.getpass()

    logged_in = robinhood.login(username=username, password=password)
    if logged_in is False:
        password = ""
        print("Invalid username or password.  Try again.\n")

# test = robinhood.adjusted_equity_previous_close()
# some = robinhood.get_user_info()
# print(some)


auto_trade()

