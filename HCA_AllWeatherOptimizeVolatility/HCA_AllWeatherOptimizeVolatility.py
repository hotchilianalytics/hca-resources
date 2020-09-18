# Source: adapted from various algos on quantopian
# HCA Conversion Date: 09-05-2020
# Conversion Author: Anthony garner


import matplotlib.pyplot as plt
import numpy as np
import math


from zipline.api import order, cancel_order, get_open_orders, symbol, symbols, date_rules, time_rules, order_target_percent, record, schedule_function, get_datetime
from trading_calendars import get_calendar

def initialize(context):
    schedule_function(func=trade, date_rule=date_rules.every_day(),
                      time_rule=time_rules.market_open(),half_days=True)
    context.asserts = symbols('SPY','IEF')

    context.rebalance_date = 0
    context.fired = False
    context.rebalance_inteval = 'M'#'Q', #'D', #'M' #'Q' #'Y'

    context.asserts_position = [0.5, 0.5]
    context.volatility_policy = True
    #unused if volatility_policy is false
    context.volatility_days = 252
    context.volatility_price_history = 66
    #set at less than 1 to ensure no leverage
    context.leverage_buffer=0.90
    
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


    # Compute historical volatility  
def compute_volatility(price_history, days):  
    # Compute daily returns  
    daily_returns = price_history.pct_change().dropna().values  
    # Compute daily volatility  
    historical_vol_daily = np.std(daily_returns,axis=0)  
    # Convert daily volatility to annual volatility, assuming 252 trading days  
    historical_vol_annually = historical_vol_daily*math.sqrt(days)  
    # Return estimate of annual volatility  
    return historical_vol_annually

def compute_asserts_volatility(context, data):
    price_history = data.history(context.asserts, "price", context.volatility_price_history, "1d")
    vol = 1.0/(compute_volatility(price_history, context.volatility_days))
    #print("vol: " + str(vol))
    sum = np.sum(vol)
    context.asserts_position = vol / sum
    #print("asserts_position: " + str(context.asserts_position))

def init_portfolio(context, data):
    if context.volatility_policy:
        compute_asserts_volatility(context, data)
    for i in range(0, len(context.asserts)):
        #print("rebalance " + context.asserts[i].symbol + " to:" + str(context.asserts_position[i]*100) + "%")
        order_target_percent(context.asserts[i], context.asserts_position[i]* context.leverage_buffer)    
        
def rebalance(context, data):
    if context.volatility_policy:
        compute_asserts_volatility(context, data)
    for i in range(0, len(context.asserts)):
        if data.can_trade(context.asserts[i]):
            #print("rebalance " + context.asserts[i].symbol + " to:" + str(context.asserts_position[i]*100) + "%")
            order_target_percent(context.asserts[i], context.asserts_position[i]* context.leverage_buffer)    
def trade(context, data):
    if not context.fired:
        context.rebalance_date = get_datetime()
        #print("build portfolio at " + str(context.rebalance_date))
        init_portfolio(context, data)
        context.fired = True
    else:
        now = get_datetime()
        if (need_rebalance(context, now)):
            #print("new rebalance arrivid:" + str(now))
            context.rebalance_date = now
            rebalance(context, data)
