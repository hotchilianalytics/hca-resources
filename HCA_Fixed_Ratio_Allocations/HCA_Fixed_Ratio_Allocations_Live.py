# HCA Live-Trade Conversion: Date:2020-08-13
# HCA Live-Simulation: Conversion Date: 08-13-2020
# Updated 09-03-2020
# Conversion Author: Anthony Garner

# HCA Original Code Source: Quantopian, various
# ------------ Start: HCA: zipline includes ------------------ 
from zipline.api import symbol, get_open_orders, order, order_target_percent
import numpy as np

# Start:Zipline Builtin Functions
def initialize(context):
    pass

def handle_data(context, data):
    if (not context.ORDERS_DONE):
        context.ORDERS_DONE = True
        trade(context, data) #Name of the original algo trading function
    else:
        print("Exiting: Zipline-broker: context.account : {}".format(context.portfolio))
        exit()
def before_trading_start(context, data):
    c = context
    c.ORDERS_DONE       = False #No Orders done yet today
    c.all_orders = {}        
# End:Zipline Builtin Functions

def trade(context,data):
    stocks     = [symbol('QQQ'), symbol('XLP'),symbol('IEF'),symbol('TLT')]
    proportion = [0.25, 0.25, 0.25, 0.25]
    lev        = 0.9 #Should allow for a small percentage of Cash, to enable ordering fluctuations without having order cancelled.

    ### ajjc: Find a way to return if already traded today
    print("TradingLinkData: Zipline-broker: context.portfolio : {}".format(context.portfolio))
    print("TradingLinkData: IB-Account    : context.account   : {}".format(context.account))

    acct_liq    = context.portfolio.starting_cash #Same as IB net_liquidation
    acct_invest = lev * acct_liq
    positions      = context.broker.positions
    
    # Sell any existing positions which are not in stocks
    for key in positions:
        if (key not in stocks and not get_open_orders(key)):
            order(key, -positions[key].amount)  
            
    # Loop through stocks and deal with the list according to whether there are existing positions or not
    for i in range(len(stocks)):
        if data.can_trade(stocks[i]) and not get_open_orders(stocks[i]):
            # If there is a position already in this stock, then rebalance it if necessary in accordance with proportion
            if stocks[i] in positions:
                current_amt = positions[stocks[i]].amount
                rebalance_amt = int(acct_invest*proportion[i] / data.current(stocks[i],'price'))
                delta_amt = rebalance_amt - current_amt
                if delta_amt != 0:
                    order(stocks[i], delta_amt) 
                else:
                    print("No new orders for : {}".format(stocks[i]))
            # If there is no existing position in the stock, take one
            if (stocks[i] not in positions and data.can_trade(stocks[i]) 
                and not get_open_orders(stocks[i])):
                amt = int(acct_invest*proportion[i] / data.current(stocks[i],'price'))
                if amt != 0:
                    order(stocks[i], amt)                                                