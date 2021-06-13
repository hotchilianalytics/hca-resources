# Vlad Code from: Aleksei Dremov  in
# https://www.quantopian.com/posts/live-slash-paper-trade-the-in-out-stragegy

# Price relative ratios (intersection) with wait days
import numpy as np

from zipline.api import order, cancel_order, get_open_orders, symbol, symbols, date_rules, time_rules, order_target_percent, record, schedule_function, get_datetime
from trading_calendars import get_calendar

def initialize(context):
    # -----------------------------------------------------------------------------------------------
    # YAHOO_SYM_LST=QQQ,TLT,IEF,SLV,GLD,XLI,XLU zipline ingest -b yahoo_direct
    c = context
    c.STOCKS = symbols('QQQ', 'URTH'); c.BONDS = symbols('TLT','IEF', 'SCHD'); c.LEV = 1.00; c.wt = {};
    c.A = symbol('SLV'); c.B = symbol('GLD'); c.C = symbol('XLI'); c.D = symbol('XLU');
    c.MKT = symbol('QQQ'); c.VOLA = 126; c.LB = 1.00; c.BULL = 1; c.COUNT = 0; c.OUT_DAY = 0; c.RET_INITIAL = 80;
# -----------------------------------------------------------------------------------------------
    
    # schedule_function(daily_check, date_rules.every_day(), time_rules.market_open(minutes = 140))
    # schedule_function(record_vars, date_rules.every_day(), time_rules.market_close())
    
def minut(context): #Minute of trading day
    dt = context.get_datetime().astimezone(pytz.timezone('US/Eastern'))
    return (dt.hour * 60) + dt.minute - 570
    
def sync_portfolio_to_broker(context, data):
    log.info("___CurrZiplinPosBef: {}".format(context.portfolio.positions)) #BUG: This is a Criticalupdate...
    if IS_LIVE:
        log.info("___CurrBrokerPosCur: {}".format(context.broker.positions)) # Look=Hook for sync of context.portfolio to context.broker.portfolio
    for x in list(context.portfolio.positions):
        #ajjc: zlb: BUG: Clean out null portfolio values. Handle this generically in zipline-broker in some way
        amt_x_port = context.portfolio.positions[x].amount
        if amt_x_port == 0: 
            del context.portfolio.positions[x]    
    log.info("___CurrZiplinPosAft: {}".format(context.portfolio.positions)) #BUG: This is a Criticalupdate...
        
def handle_data_orig(context, data):
    time_now = minut(context)
    log.info("___handle_data: {} = Current Trading Minute".format(time_now))
    sync_portfolio_to_broker(context, data)
    
def handle_data(context, data):
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
# End:Zipline Builtin Functions
        

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
    
    print("WAIT_DAYS={} RET={} exit={} c.COUNT={} c.BULL={} c.OUT_DAY={}".format(WAIT_DAYS,RET,exit,c.COUNT,c.BULL,c.OUT_DAY))
    print("Trading Weights Today: wt_stk={} wt_bnd={} wts={}".format(c.wt,wt_stk,wt_bnd))
    print("End: ---------------------------")
    
    #for sec, weight in c.wt.items():
        #order_target_percent(sec, weight)
    #record( wt_bnd = wt_bnd, wt_stk = wt_stk )

def trade(context,data,wts):
    lev = context.LEV #Should allow for a small percentage of Cash, to enable ordering fluctuations without having order cancelled.
    
    ### ajjc: Find a way to return if already traded today
    print("TradingLinkData: Zipline-broker: context.portfolio : {}".format(context.portfolio))
    print("TradingLinkData: IB-Account    : context.account   : {}".format(context.account))
    acct_liq    = context.portfolio.starting_cash #Same as IB net_liquidation
    acct_invest = lev * acct_liq   
    positions      = context.broker.positions
    
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