# Source:Code taken from various Quantopian algos with my own additions
# HCA Conversion Date: 08-14-2020
# Conversion Author: Anthony Garner

import pandas as pd
from zipline.api import (get_open_orders, order, cancel_order, symbol, symbols, date_rules, order_target_percent, record,  schedule_function)
from trading_calendars import get_calendar
import zipline.utils.events
from zipline.utils.events import (EventManager, make_eventrule, date_rules, time_rules, calendars, AfterOpen, BeforeClose)


# Simple trend following portfolio
def initialize(context):
    schedule_function(func=trade, date_rule=date_rules.every_day(),
                      time_rule=time_rules.market_open(),half_days=True)
    schedule_function(func=cancel,time_rule=time_rules.market_close(minutes=5),  
                      date_rule=date_rules.every_day(),half_days=True)  
    schedule_function(func=reorder, time_rule=time_rules.market_open(minutes=5),  
                      date_rule=date_rules.every_day(),half_days=True)
    context.asserts = symbols('SPY')
    context.bonds = symbol('SHY') 
    context.rebalance_date = 0
    context.fired = False
    context.rebalance_inteval = 'D'#'Q', #'D', #'M' #'Q' #'Y'
    context.top_n_by_momentum = pd.Series()  
    #Choose X stocks out of portfolio of Y stocks- how many stocks to hold - top X by momentum 
    context.stocks=1
    #Lookback for momentum calculation
    context.momentum_days=60
    #set at less than 1 to ensure no leverage
    context.leverage_buffer=0.99
    #Set to 0 to reject any stocks with negative momentum, set to -1 to accept stocks with negative momentum
    context.trend =0.0
    context.reorder_dict = {}  


    
def handle_data(context, data):
    record(SPY=data[symbol('SPY')].price)

def is_new_day(context, now):
    return ( (now.year > context.rebalance_date.year) or (now.month > context.rebalance_date.month) or((now.month == context.rebalance_date.month) and (now.day > context.rebalance_date.day)))             
    
def is_new_month(context, now):
    return ((now.year > context.rebalance_date.year) or ((now.year == context.rebalance_date.year) and (now.month > context.rebalance_date.month)))

def is_new_quarter(context, now):
    return ((now.year > context.rebalance_date.year) or ((now.year == context.rebalance_date.year) and (now.month == context.rebalance_date.month + 3)))
    
def is_new_year(context, now):
    return (now.year > context.rebalance_date.year)

def need_rebalance(context, now):
    return ((context.rebalance_inteval == 'Y' and is_new_year(context, now))or 
           (context.rebalance_inteval == 'Q' and is_new_quarter(context, now)) or 
           (context.rebalance_inteval == 'M' and is_new_month(context, now)) or 
           (context.rebalance_inteval == 'D' and is_new_day(context, now)))


    # Compute momentum
def compute_momentum(context,data):  
    price_history = data.history(context.asserts, "price", context.momentum_days+5, "1d")
    momentum = price_history.pct_change(context.momentum_days).iloc[-1]
    #for index,value in momentum.items():
        #print("unfiltered momentun"+" "+ str(index)+" "+ str(value) )
    context.top_n_by_momentum = momentum.nlargest(context.stocks).where(momentum>context.trend).dropna()
    #for index,value in context.top_n_by_momentum.items():
        #print("context.top_n_by_momentun"+" "+str(index)+" " + str(value) )
    return context.top_n_by_momentum

def init_portfolio(context, data):
    weights=0.0
    reserve_allocation=0.0
    compute_momentum(context, data)
    for index,value in context.top_n_by_momentum.items():
        if data.can_trade(index):
            weights =weights +1/context.stocks
            order_target_percent(index, (1/context.stocks)* context.leverage_buffer)
    #Assign weighting and an order to the reserve asset if and when appropriate
    if weights <1 and data.can_trade(context.bonds):
        reserve_allocation=1-weights
        order_target_percent(context.bonds, reserve_allocation* context.leverage_buffer)     
        
def rebalance(context, data):
    weights=0.0
    reserve_allocation=0.0
    compute_momentum(context, data)
    for x in context.portfolio.positions:
        if (x not in context.top_n_by_momentum and x != context.bonds):
            order_target_percent(x, 0)            
    
    for index,value in context.top_n_by_momentum.items():
        if data.can_trade(index)and index != context.bonds:
            weights =weights +1/context.stocks
            order_target_percent(index, (1/context.stocks)*context.leverage_buffer)
        elif data.can_trade(index) and index != context.bonds: 
            order_target_percent(index, 0)
    #Assign weighting and an order to the reserve asset if and when appropriate        
    if data.can_trade(context.bonds):
        reserve_allocation=1-weights
        order_target_percent(context.bonds, reserve_allocation* context.leverage_buffer)        

#Will be called daily. 
def trade(context, data):
    if not context.fired:
        context.rebalance_date = context.get_datetime()
        print("build portfolio at " + str(context.rebalance_date))
        init_portfolio(context, data)
        context.fired = True
        now = context.get_datetime()
    else:
        now = context.get_datetime()
        if (need_rebalance(context, now)):
            #print("new rebalance arrivied:" + str(now))
            rebalance(context, data)
            context.rebalance_date = now
    #open_orders = get_all_open_orders()  
    #for order in open_orders:  
                #print("Rebalance Order {0:s} for {1:,d} shares" 
            #.format(order.sid.symbol,order.amount))  
#Called Daily to replace/re-order partially or unfilled orders
def cancel(context, data):  
    open_orders = get_all_open_orders()  
    for order in open_orders:  
        #print("X CANCELED {0:s} with {1:,d} / {2:,d} filled" 
            #.format(order.sid.symbol,  
                    #order.filled,  
                    #order.amount))  
        cancel_order(order)  
        context.reorder_dict[order.sid] = order.amount - order.filled

def get_all_open_orders():  
    from itertools import chain  
    orders = chain.from_iterable(get_open_orders().values())  
    return list(orders)  
#Called Daily to replace/re-order partially or unfilled orders
def reorder(context, data):  
    for stock, amount in context.reorder_dict.items():  
        order(stock, amount)  
        #print("Reorder {stock} {amount}".format(stock=stock, amount=amount))  
    context.reorder_dict = {}
    
#def analyze(context, perf):
    #ax1 = plt.subplot(211)
    #perf.portfolio_value.plot(ax=ax1)
    #ax2 = plt.subplot(212, sharex=ax1)
    #perf.SPY.plot(ax=ax2)
    #plt.gcf().set_size_inches(18, 8)
    #plt.show()