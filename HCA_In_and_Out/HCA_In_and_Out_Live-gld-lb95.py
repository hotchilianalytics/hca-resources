# Vlad Code from: Aleksei Dremov  in
# https://www.quantopian.com/posts/live-slash-paper-trade-the-in-out-stragegy

# Price relative ratios (intersection) with wait days
import numpy as np
import pandas as pd

from datetime import datetime
import pytz
from pytz import timezone as _tz  # Python only does once, makes this portable.

from zipline.api import order, cancel_order, get_order, get_open_orders, symbol, symbols, date_rules, time_rules, order_target_percent, record, schedule_function, get_datetime, set_benchmark
from trading_calendars import get_calendar

IS_LIVE = True #True #False= simulation for bot(typically 2 years.)
import pathlib as pl

from pathlib import Path
import pprint as pp

import time


IS_FIRST_DAY = False

p                = pl.Path('/home/hca-ws2004/hca/hca-resources/HCA_In_and_Out/')
p.mkdir(exist_ok = True, parents=True)
#permanent_file   = p / f'in_and_out_live_state-gld.csv'
permanent_file   = p / f'in_and_out_live_state-lb95-gld.csv'



def initialize(context):
    # -----------------------------------------------------------------------------------------------
    # YAHOO_SYM_LST=QQQ,TLT,IEF,SLV,GLD,XLI,XLU zipline ingest -b yahoo_direct
    # HNDL - ETF with: -Min dividend 7% -Mix of funds -23% leverage
    c = context
    #set_benchmark(symbol("SPY"))        
    ###if not ('IS_PERSIST' in dir(c)): #
    #No context state available, so set it.
    print("Init: Initial. No persistent context yet. context={}".format(c))
    if not IS_LIVE: # For simulation bot, init state file    
        if permanent_file.exists():
            permanent_file.unlink()   # Remove old state file from previous sim
        else:
            permanent_file.touch() #If file does not exist, create it.
        IS_FIRST_DAY = True #With sim, alwasys start with a new state file.
    else: #Live
        if permanent_file.exists():
            IS_FIRST_DAY = False
        else:
            IS_FIRST_DAY = True
        
    c.STOCKS = symbols('IWB' , 'QQQ'); c.BONDS = symbols('IEF', 'GLD'); c.LEV =0.95; c.wt = {};        
    #c.STOCKS = symbols('QQQ', 'SCHD'); c.BONDS = symbols('TLT','IEF'); c.LEV = 1.00; c.wt = {}; #TMF
    #c.STOCKS = symbols('QQQ', 'URTH'); c.BONDS = symbols('TLT','IEF', 'SCHD'); c.LEV = 1.00; c.wt = {};
    c.A = symbol('SLV'); c.B = symbol('GLD'); c.C = symbol('XLI'); c.D = symbol('XLU');
    c.MKT = symbol('QQQ'); c.VOLA = 126; c.LB = 0.98; c.BULL = 0; c.COUNT = 0; c.OUT_DAY = 0; c.RET_INITIAL = 80;
    #Before 2021-07-29: c.LB = 0.95 c.LEV=1.00
    #Algo params
    c.ratio_ab=0.0;c.ratio_cd=0.0;c.exit=False
    if IS_FIRST_DAY: #Initialize default drop through In-and-Out BULL flag. 
        c.BULL =1
    else:
        c.BULL = 0  # Today's init. Will read yesterday's value from from permanent_file. 
    ###else:
        ###print("Init: Initial. Persistent Context Available (from strategy.state): context={}".format(c))
   # -----------------------------------------------------------------------------------------------
    #if not IS_LIVE:
    #   schedule_function(daily_check, date_rules.every_day(), time_rules.market_open(minutes = 140))
    #    schedule_function(record_vars, date_rules.every_day(), time_rules.market_close())
    
def minut(context): #Minute of trading day
    dt = context.get_datetime().astimezone(pytz.timezone('US/Eastern'))
    return (dt.hour * 60) + dt.minute - 570
    
def sync_portfolio_to_broker(context, data):
    ###log.info("___CurrZiplinPosBef: {}".format(context.portfolio.positions)) #BUG: This is a Criticalupdate...
    if IS_LIVE:
        log.info("___CurrBrokerPosCur: {}".format(context.broker.positions)) # Look=Hook for sync of context.portfolio to context.broker.portfolio
    for x in list(context.portfolio.positions):
        #ajjc: zlb: BUG: Clean out null portfolio values. Handle this generically in zipline-broker in some way
        amt_x_port = context.portfolio.positions[x].amount
        if amt_x_port == 0: 
            del context.portfolio.positions[x]    
    ###log.info("___CurrZiplinPosAft: {}".format(context.portfolio.positions)) #BUG: This is a Criticalupdate...

def cancel_open_orders(context):
    for security in get_open_orders():
        for order in get_open_orders(security):
            cancel_order(order)
            print('Security {} had open orders: now cancelled'.format(str(security)))

        
def handle_data_orig(context, data):
    time_now = minut(context)
    ###log.info("___handle_data: {} = Current Trading Minute".format(time_now))
    sync_portfolio_to_broker(context, data)
    
def handle_data(context, data):
    if (not context.ORDERS_DONE):
        context.ORDERS_DONE = True
        daily_check(context,data) #Name of the original algo trading function
        trade(context,data,context.wt)
        record_vars(context, data)        
    else:
        print("Exiting: zipline-broker: context.portfolio : {}".format(context.portfolio))
        cancel_open_orders(context)
        exit()
        
from zipline.data.benchmarks import get_benchmark_returns       
def before_trading_start(context, data):
    c = context
    c.ORDERS_DONE       = False #No Orders done yet today
    c.all_orders = {}
    c.traded_df    = pd.DataFrame()        
    
    if permanent_file.exists():
        #read_csv for past values of state, and set COUNT and OUT_DAY
        try:
            c.traded_df = c.traded_df.from_csv(permanent_file) # Read in previous state of parameters.
            c.COUNT   = c.traded_df.iloc[-1].COUNT
            c.OUT_DAY = c.traded_df.iloc[-1].OUT_DAY
            c.BULL = c.traded_df.iloc[-1].BULL
            ###pp.pprint(c.traded_df.iloc[-1])
        except:
            pp.pprint(f"before_trading_start: {permanent_file} is empty or ill formed. Using initial values.")
            
        
# End:Zipline Builtin Functions
        

def daily_check(context,data):
    c = context
    #global c.BULL, c.COUNT, OUT_DAY
    # Start signal computation    
    vola     = data.history(c.MKT, 'price',  c.VOLA + 1, '1d').pct_change().std() * np.sqrt(252)
    WAIT_DAYS= int(vola * c.RET_INITIAL)
    RET      = int((1.0 - vola) * c.RET_INITIAL)
    P        = data.history([c.A,c.B,c.C,c.D], 'price',  RET + 2, '1d').iloc[:-1].dropna()
    ratio_ab = (P[c.A].iloc[-1] / P[c.A].iloc[0]) / (P[c.B].iloc[-1] / P[c.B].iloc[0])
    ratio_cd = (P[c.C].iloc[-1] / P[c.C].iloc[0]) / (P[c.D].iloc[-1] / P[c.D].iloc[0])
    exit     = (ratio_ab < c.LB) and (ratio_cd < c.LB)
    if exit: c.BULL = 0; c.OUT_DAY = c.COUNT;
    elif (c.COUNT >= (c.OUT_DAY + WAIT_DAYS)): c.BULL = 1
    c.COUNT += 1
    wt_stk   = c.LEV if c.BULL else 0;
    wt_bnd   = 0 if c.BULL else c.LEV;
    for sec in c.STOCKS: c.wt[sec] = wt_stk / len(c.STOCKS);
    for sec in c.BONDS: c.wt[sec]  = wt_bnd / len(c.BONDS)
    today    = c.get_datetime().astimezone(pytz.timezone('US/Eastern')) #Current simulation time.
    #today   = datetime.today() #Current day live

    new_row     = pd.DataFrame(data=[[c.COUNT, WAIT_DAYS, RET, ratio_ab, ratio_cd, exit, c.BULL, c.OUT_DAY]], columns=['COUNT', 'WAIT_DAYS','RET', 'ratio_ab', 'ratio_cd', 'exit','BULL','OUT_DAY'],  index=[today])
    c.traded_df = pd.concat([c.traded_df, pd.DataFrame(new_row)], ignore_index=False)
    c.traded_df.to_csv(permanent_file, index_label='Date',)
    ###print("c.traded_df: {}".format(c.traded_df))
    #with open(permanent_file, 'a') as filehandle:
    #   filehandle.write('\n' + 'Hello, world!\n')
    
    print("WAIT_DAYS={} RET={} ratio_ab={} ratio_cd={} exit={} c.COUNT={} c.BULL={} c.OUT_DAY={}".format(WAIT_DAYS,RET, ratio_ab, ratio_cd, exit,c.COUNT,c.BULL,c.OUT_DAY))
    print("Trading Weights Today: wt_stk={} wt_bnd={} wts={}".format(c.wt,wt_stk,wt_bnd))
    print("End: ---------------------------")
    
    #for sec, weight in c.wt.items():
        #order_target_percent(sec, weight)
    #record( wt_bnd = wt_bnd, wt_stk = wt_stk )

def trade(context,data,wts):
    lev = context.LEV #Should allow for a small percentage of Cash, to enable ordering fluctuations without having order cancelled.
    
    ### ajjc: Find a way to return if already traded today
    #print("TradingLinkData: Zipline-broker: context.portfolio : {}".format(context.portfolio))
    #print("TradingLinkData: IB-Account    : context.account   : {}".format(context.account))
    if IS_LIVE:
        acct_liq    = context.portfolio.starting_cash #Same as IB net_liquidation
    else:
        acct_liq    = context.portfolio.portfolio_value #Same as IB net_liquidation
    acct_invest = lev * acct_liq
    if IS_LIVE:
        positions   = context.broker.positions
    else:
        positions   = context.portfolio.positions
    
    # Get rid of positions not in wts
    for key in positions:
        if (key not in wts and not get_open_orders(key)):
            amt = -positions[key].amount
            order_id = order(key, amt)
            print("Clear Position Order{}: stk={} amt={} not fully filled".format(order_id,key,amt))
            
            if IS_LIVE:
                #Check order is done within 60 sec, to properly order the order queue(e.g. sells before buys)
                if not check_order_fill(order_id=order_id, amt=amt, timeout=60):
                    print("{} WARNING: Order{} stk={} amt={} not fully filled".format(order_id,key,amt))
        
    for stk,weight in wts.items():
        if data.can_trade(stk) and not get_open_orders(stk):
            if stk in positions:
                current_amt = positions[stk].amount
                rebalance_amt = int(acct_invest*(weight) / data.current(stk,'price'))
                delta_amt = rebalance_amt - current_amt
                if delta_amt != 0:
                    #Check order is done within 60 sec, to properly order the order queue(e.g. sells before buys)
                    order_id = order(stk, delta_amt)
                    print("Order{}: stk={} amt={} not fully filled".format(order_id,stk,delta_amt))
                    
                    if IS_LIVE:                    
                        #Check order is done within 60 sec, to properly order the order queue(e.g. sells before buys)
                        if not check_order_fill(order_id=order_id, amt=delta_amt, timeout=60):
                            print("WARNING: Order{} stk={} amt={} not fully filled".format(order_id,stk,amt))
                else:
                    print("No new orders for : {}".format(stk))

            if (stk not in positions and data.can_trade(stk) 
                and not get_open_orders(stk)):
                
                amt = int(acct_invest*(weight) / data.current(stk,'price'))
                
                order_id = order(stk, amt)
                if IS_LIVE:
                    #Check order is done within 60 sec, to properly order the order queue(e.g. sells before buys)
                    if not check_order_fill(order_id=order_id, amt=amt, timeout=60):
                        print("WARNING: Order{} stk={} amt={} not fully filled".format(order_id,stk,amt))
                                    
    mkt_time = context.get_datetime().astimezone(pytz.timezone('US/Eastern'))
    #context.ORDERS_DONE = True
    print("Orders_Done= {} Market Time={}: Trading done for today".format(context.ORDERS_DONE, mkt_time))
    
     

def check_order_fill(order_id="", amt=0, timeout=60):
    is_order_done = False    
    order_chk_time = 0
    while not is_order_done:                        
        time.sleep(1)
        order_chk_time += 1
        order_status = get_order(order_id)
        if order_status: 
            if (order_status.status):
            #if (order_status.filled==amt): #Doesn't work for sell
                is_order_done = True
                print("Order{}-is_order_done={}".format(order_id, is_order_done))
                continue
            else:
                if order_chk_time > timeout:
                    print("Order{}-is_order_done={}  amt={} filled={}".format(order_id, is_order_done, amt, order_status.filled))
                    
                    return  False # Timeout for filling order
                else:
                    print("Order{}-is_order_done={}  amt={} status={} order_chk_time={}".format(order_id, is_order_done,  amt, order_status.status, order_chk_time))                  
        else:
            is_order_done = True # No order to fill
    return True # order done
    
def record_vars(context, data):
    record(leverage = context.account.leverage)
