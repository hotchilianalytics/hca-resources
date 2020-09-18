# Source: adapted from various algos on quantopian
# HCA Conversion Date: 08-13-2020
# Conversion Author: Anthony garner

# Simple rebalanced portfolio
import matplotlib.pyplot as plt

from zipline.api import symbol, symbols, date_rules, time_rules, order_target_percent, record, schedule_function, get_datetime
from trading_calendars import get_calendar

def initialize(context):
    schedule_function(func=trade,date_rule=date_rules.every_day(),time_rule=time_rules.market_open(),half_days=True)
    context.asserts = symbols('SPY','SHY','TLT','GLD')
    context.asserts_position = [0.25, 0.25,0.25,0.25]
    context.rebalance_inteval = 'Q'#'Q', #'D', #'M' #'Q' #'Y'
    context.rebalance_date = 0
    context.fired = False
    
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


def init_portfolio(context, data):
    for i in range(0, len(context.asserts)):
        if data.can_trade(context.asserts[i]):
            #log.debug("rebalance " + context.asserts[i].symbol + " to:" + str(context.asserts_position[i]*100) + "%")
            order_target_percent(context.asserts[i], context.asserts_position[i])

def rebalance(context, data):
    for i in range(0, len(context.asserts)):
        if data.can_trade(context.asserts[i]):
            #log.debug("rebalance " + context.asserts[i].symbol + " to:" + str(context.asserts_position[i]*100) + "%")
            order_target_percent(context.asserts[i], context.asserts_position[i])
        

# Will be called on every trade event for the securities you specify. 
def trade(context, data):
    if not context.fired:
        context.rebalance_date = get_datetime()
        #log.info("build portfolio at " + str(context.rebalance_date))
        init_portfolio(context, data)
        context.fired = True
        now = get_datetime()
    else:
        now = get_datetime()
        if (need_rebalance(context, now)):
            #log.info("new rebalance arrivied:" + str(now))
            rebalance(context, data)
            context.rebalance_date = now
    
def analyze(context, perf):
    ax1 = plt.subplot(211)
    perf.portfolio_value.plot(ax=ax1)
    ax2 = plt.subplot(212, sharex=ax1)
    perf.SPY.plot(ax=ax2)
    plt.gcf().set_size_inches(18, 8)
    plt.show()