# HCA Live-Trade Conversion: Date:2020-08-13
# HCA Live-Simulation: Conversion Date: 08-13-2020
# Amended in Accordance with decision to use order: 2020-08-29
# Conversion Author: Anthony Garner

from zipline.api import symbol,symbols, get_open_orders, order
import numpy as np
import pandas as pd

# Start:Zipline Builtin Functions
def initialize(context):
    context.asserts  = symbols('SPY','ZSL', 'KOLD', 'GLD')
    context.bonds    = symbol('SHY')
    context.universe = symbols('SPY','ZSL', 'KOLD', 'GLD', 'SHY')
    
    context.top_n_by_momentum = pd.Series() 
    #Choose X stocks out of portfolio of Y stocks- how many stocks to hold - top X by momentum 
    context.num_stocks=3
    #Lookback for momentum calculation
    context.momentum_days=60
    #Set context.trend to 0 to reject any stocks with negative momentum, set to -1 to accept stocks with negative momentum
    context.trend =0.0
    context.stocks=[] 

    # Compute momentum
def compute_momentum(context,data):  
    price_history = data.history(context.asserts, "price", context.momentum_days+5, "1d")
    momentum = price_history.pct_change(context.momentum_days).iloc[-1]
    context.top_n_by_momentum = momentum.nlargest(context.num_stocks).where(momentum>context.trend).dropna()
    return context.top_n_by_momentum

def cancel_open_orders_and_clear_non_universe_positions(context):
    from zipline.api import get_open_orders, order

    for security in get_open_orders():
        for order in get_open_orders(security):
            cancel_order(order)
            print('Security {} had open orders: now cancelled'.format(str(security)))
            
    positions      = context.broker.positions
    
    # Get rid of positions not in current universe
    for key in positions:
        if (key not in context.universe and not get_open_orders(key)):
            print('Dump {}: Shares: {}'.format(key,-positions[key].amount))
            order(key, -positions[key].amount)      

        
def handle_data(context, data):
    if (not context.ORDERS_DONE):
        context.ORDERS_DONE = True
        #cancel_open_orders()
        cancel_open_orders_and_clear_non_universe_positions(context)
        trade(context, data) #Name of the original algo trading function
    else:
        print("Exiting: Zipline-broker: context.portfolio : {}".format(context.portfolio))
        exit()
        
def before_trading_start(context, data):
    c = context
    c.ORDERS_DONE       = False #No Orders done yet today
    c.all_orders = {} 
    compute_momentum(context, data)
    context.stocks=[]
    for index,value in context.top_n_by_momentum.items():
            context.stocks.append(index)
    context.stocks.append(context.bonds)
# End:Zipline Builtin Functions

def trade(context,data):
    lev = 0.9 #Should allow for a small percentage of Cash, to enable ordering fluctuations without having order cancelled.
    stocks = context.stocks
    num_stocks = context.num_stocks
    ### ajjc: Find a way to return if already traded today
    print("TradingLinkData: Zipline-broker: context.portfolio : {}".format(context.portfolio))
    print("TradingLinkData: IB-Account    : context.account   : {}".format(context.account))
    acct_liq    = context.portfolio.starting_cash #Same as IB net_liquidation
    acct_invest = lev * acct_liq   
    positions      = context.broker.positions   
    
    for key in positions:
        if (key not in stocks and key != context.bonds and not get_open_orders(key)):
            order(key, -positions[key].amount)      
        
    for i in range(len(stocks)):
        if data.can_trade(stocks[i]) and not get_open_orders(stocks[i]) and stocks[i] != context.bonds:
            
            if stocks[i] in positions:
                
                current_amt = positions[stocks[i]].amount
                rebalance_amt = int(acct_invest*(1/num_stocks) / data.current(stocks[i],'price'))
                delta_amt = rebalance_amt - current_amt
                
                if delta_amt != 0:
                    order(stocks[i], delta_amt) 
                else:
                    print("No new orders for : {}".format(stocks[i]))
            
            if (stocks[i] not in positions and data.can_trade(stocks[i]) 
                and not get_open_orders(stocks[i]) and stocks[i] != context.bonds):
                
                amt = int(acct_invest*(1/context.num_stocks) / data.current(stocks[i],'price'))
                order(stocks[i], amt)                                                
        
        if data.can_trade(stocks[i]) and not get_open_orders(stocks[i]) and stocks[i] == context.bonds: 
            
            rebalance_amt = int(acct_invest*(1-(1/context.num_stocks)*(len(stocks)-1)) / data.current(stocks[i],'price'))
            
            if stocks[i] in positions:  
                
                current_amt = positions[stocks[i]].amount
                delta_amt = rebalance_amt - current_amt
                
                if delta_amt != 0:
                    order(stocks[i], delta_amt)
                else:
                    print("No new orders for : {}".format(stocks[i]))    
            else:
                
                if rebalance_amt > 0:
                    order(stocks[i], rebalance_amt)
            