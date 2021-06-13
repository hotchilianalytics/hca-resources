# Vlad Code from: Aleksei Dremov  in
# https://www.quantopian.com/posts/live-slash-paper-trade-the-in-out-stragegy

# Price relative ratios (intersection) with wait days

import sys, os, inspect
import numpy  as np
import pandas as pd
from datetime import datetime
import pytz
from pytz import timezone as _tz  # Python only does once, makes this portable.
                                  #   Move to top of algo for better efficiency.
import logbook
                                    
from zipline.api import order, cancel_order, get_open_orders, symbol, symbols, date_rules, time_rules, order_target_percent, record, schedule_function, get_datetime
from trading_calendars import get_calendar
#Globals
DEBUG = False #True

###########################################################
# Logging. Following imports are not approved in Quantopian

log_format = "{record.extra[algo_dt]}  {record.message}"

zipline_logging = logbook.NestedSetup([
    logbook.StreamHandler(sys.stdout, level=logbook.INFO, format_string=log_format),
    logbook.StreamHandler(sys.stdout, level=logbook.DEBUG, format_string=log_format),
    logbook.StreamHandler(sys.stdout, level=logbook.WARNING, format_string=log_format),
    logbook.StreamHandler(sys.stdout, level=logbook.NOTICE, format_string=log_format),
    logbook.StreamHandler(sys.stdout, level=logbook.ERROR, format_string=log_format),
    #logbook.StreamHandler(sys.stderr, level=logbook.ERROR, format_string=log_format),
    logbook.RotatingFileHandler(filename='/home/hca-ws2004/hca/hca-resources/HCA_In_and_Out/zipline_rotating.log')  
])
zipline_logging.push_application()
log = logbook.Logger('Main Logger')
permanent_file = '/home/hca-ws2004/hca/hca-resources/HCA_In_and_Out/in_and_out_state.txt'

def minut(context): #Minute of trading day
    dt = context.get_datetime().astimezone(pytz.timezone('US/Eastern'))
    return (dt.hour * 60) + dt.minute - 570


#### Start: Zipline built-in Functions
def initialize(context):
    # -----------------------------------------------------------------------------------------------
    # YAHOO_SYM_LST=QQQ,TLT,IEF,SLV,GLD,XLI,XLU zipline ingest -b yahoo_direct
    c = context
    #orig c.STOCKS = symbols('QQQ'); c.BONDS = symbols('TLT','IEF'); c.LEV = 1.00; c.wt = {};
    #ajjc
    c.STOCKS = symbols('QQQ', 'URTH'); c.BONDS = symbols('TLT','IEF','SCHD'); c.LEV = 1.00; c.wt = {};
    c.A = symbol('SLV'); c.B = symbol('GLD'); c.C = symbol('XLI'); c.D = symbol('XLU');
    c.MKT = symbol('QQQ'); c.VOLA = 126; c.LB = 1.00; c.BULL = 1; c.COUNT = 0; c.OUT_DAY = 0; c.RET_INITIAL = 80;
# -----------------------------------------------------------------------------------------------

    schedule_function(daily_check, date_rules.every_day(), time_rules.market_open(minutes = 140))
    schedule_function(record_vars, date_rules.every_day(), time_rules.market_close())
    
    # Create persistent state data frame 
    c.traded_df    = pd.DataFrame()
    today = context.get_datetime().astimezone(pytz.timezone('US/Eastern')) #Current simulation time.
    #today          = datetime.today() #Current day's live time. NOT the simulation time.
    #today = context.datetime.now(tz='US/Eastern')
    WAIT_DAYS=0;RET=0;exit=False #Init
    c.traded_df  = pd.DataFrame(data=[[c.COUNT, WAIT_DAYS, RET, exit, c.BULL, c.OUT_DAY]], columns=['COUNT', 'WAIT_DAYS','RET','exit','BULL','OUT_DAY'], index=[today])
    print("Init:c.traded_df={}".format(c.traded_df))
                
def handle_data(context, data):
    time_now = minut(context)
    log.info("___handle_data: {} = Current Trading Minute".format(time_now))
     
def handle_data_live(context, data):
    if (not context.ORDERS_DONE):
        context.ORDERS_DONE = True
        daily_check(context,data) #Name of the original algo trading function
        trade(context,data,context.wt)
        record_vars(context, data)        
    else:
        print("Exiting: zipline-broker: context.portfolio : {}".format(context.portfolio))
        exit()
        
def before_trading_start(context, data):
    c = context
    c.ORDERS_DONE       = False #No Orders done yet today
    c.all_orders = {} 
    
#### End: Zipline built-in Functions
        

def daily_check(context,data):
    c = context
    #global c.BULL, c.COUNT, OUT_DAY
    vola = data.history(c.MKT, 'price',  c.VOLA + 1, '1d').pct_change().std() * np.sqrt(252)
    WAIT_DAYS = int(vola * c.RET_INITIAL)
    RET = int((1.0 - vola) * c.RET_INITIAL)
    P = data.history([c.A,c.B,c.C,c.D], 'price',  RET + 2, '1d').iloc[:-1].dropna()
    ratio_ab = (P[c.A].iloc[-1] / P[c.A].iloc[0]) / (P[c.B].iloc[-1] / P[c.B].iloc[0])
    ratio_cd = (P[c.C].iloc[-1] / P[c.C].iloc[0]) / (P[c.D].iloc[-1] / P[c.D].iloc[0])
    exit = ratio_ab < c.LB and ratio_cd < c.LB
    if exit: c.BULL = 0; c.OUT_DAY = c.COUNT;
    elif (c.COUNT >= c.OUT_DAY + WAIT_DAYS): c.BULL = 1
    c.COUNT += 1
    wt_stk = c.LEV if c.BULL else 0;
    wt_bnd = 0 if c.BULL else c.LEV;
    for sec in c.STOCKS: c.wt[sec] = wt_stk / len(c.STOCKS);
    for sec in c.BONDS: c.wt[sec] = wt_bnd / len(c.BONDS)
    today       = c.get_datetime().astimezone(pytz.timezone('US/Eastern')) #Current simulation time.
    #today      = datetime.today() #Current day live

    new_row     = pd.DataFrame(data=[[c.COUNT, WAIT_DAYS, RET, exit, c.BULL, c.OUT_DAY]], columns=['COUNT', 'WAIT_DAYS','RET','exit','BULL','OUT_DAY'], index=[today])
    c.traded_df = pd.concat([c.traded_df, pd.DataFrame(new_row)], ignore_index=False)
    c.traded_df.to_csv(permanent_file)
    print("c.traded_df: {}".format(c.traded_df))
    #with open(permanent_file, 'a') as filehandle:
    #   filehandle.write('\n' + 'Hello, world!\n')
    
    print("WAIT_DAYS={} RET={} exit={} c.COUNT={} c.BULL={} c.OUT_DAY={}".format(WAIT_DAYS,RET,exit,c.COUNT,c.BULL,c.OUT_DAY))
    print("Trading Weights Today: wt_stk={} wt_bnd={} wts={}".format(c.wt,wt_stk,wt_bnd))
    
    trade(context,data,c.wt)
    #for sec, weight in c.wt.items():
        #order_target_percent(sec, weight)
    #record( wt_bnd = wt_bnd, wt_stk = wt_stk )

def trade(context,data,wts):
    lev = context.LEV #Should allow for a small percentage of Cash, to enable ordering fluctuations without having order cancelled.
    if DEBUG:
        ### ajjc: Find a way to return if already traded today
        print("TradingLinkData: Zipline-broker: context.portfolio : {}".format(context.portfolio))
        print("TradingLinkData: IB-Account    : context.account   : {}".format(context.account))

    #acct_liq    = context.portfolio.starting_cash #Same as IB net_liquidation when measured daily
    acct_liq    = context.portfolio.portfolio_value #Same as IB net_liquidation
    acct_invest = lev * acct_liq   
    positions   = context.portfolio.positions
    #Live positions      = context.broker.positions
    
    # Get rid of positions not in wts
    for key in positions:
        if (key not in wts and not get_open_orders(key)):
            order(key, -positions[key].amount)      
        
    for stk,weight in wts.items():
        if data.can_trade(stk) and not get_open_orders(stk):
            if stk in positions:
                current_amt = positions[stk].amount
                rebalance_amt = int(acct_invest*(weight) / data.current(stk,'price'))
                delta_amt = rebalance_amt - current_amt
                if delta_amt != 0:
                    order(stk, delta_amt) 
                else:
                    print("No new orders for : {}".format(stk))

            if (stk not in positions and data.can_trade(stk) 
                and not get_open_orders(stk)):
                
                amt = int(acct_invest*(weight) / data.current(stk,'price'))
                order(stk, amt)                                                    

def record_vars(context, data):
    record(leverage = context.account.leverage)