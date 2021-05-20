#!/usr/bin/env python
from __future__ import absolute_import, unicode_literals

from zipline.pipeline.data import USEquityPricing as USEP
from zipline.pipeline.factors import Returns, AverageDollarVolume

from zipline import run_algorithm
from zipline.api import symbol, symbols, attach_pipeline, date_rules, order_target_percent, pipeline_output, record, schedule_function

from zipline import extension_args as  ext_args  # Access to commandline arguments

from zipline.finance import commission, slippage

from zipline.pipeline import Pipeline
from zipline.pipeline import factors, filters, classifiers
from zipline.pipeline.factors import CustomFactor, SimpleMovingAverage, AverageDollarVolume, Returns, RSI
from zipline.pipeline.filters import StaticAssets

from trading_calendars import get_calendar


#from alphatools.research import run_pipeline, make_factor_plot, make_quantile_plot, loaders
from alphatools.fundamentals import Fundamentals


from alphatools.ics import Sector, SubIndustry


import zipline.utils.events
from zipline.utils.events import (
    EventManager,
    make_eventrule,
    date_rules,
    time_rules,
    calendars,
    AfterOpen,
    BeforeClose
)

from zipline.api import get_open_orders, order, cancel_order
from zipline.api import (slippage,
                         commission,
                         set_slippage,
                         set_commission,
                         record,
                         sid,
                         symbol)
import pandas as pd
import numpy as np
import scipy.stats as stats

from six import viewkeys
#import matplotlib.pyplot as plt
from datetime import datetime
import pytz
from pytz import timezone as _tz  # Python only does once, makes this portable.
                    #   Move to top of algo for better efficiency.
import sys, os
import json # For pretty-printing results

IS_LIVE = False #False #True #True #False #False #True
DEBUG = False
MINUTES_TO_REBAL = 1

# Algo Parameter that is number in top indebeted assets, for pipeline.
NUM_TOP_INDEBTED = 10 #21 #25 #15

# Logging. Following imports are not approved in Quantopian
####################################################################################

import logbook
import sys
import pathlib as pl

log_format = "{record.extra[algo_dt]}  {record.message}"

zipline_logging = logbook.NestedSetup([
    logbook.StreamHandler(sys.stdout, level=logbook.INFO, format_string=log_format),
    logbook.StreamHandler(sys.stdout, level=logbook.DEBUG, format_string=log_format),
    logbook.StreamHandler(sys.stdout, level=logbook.WARNING, format_string=log_format),
    logbook.StreamHandler(sys.stdout, level=logbook.NOTICE, format_string=log_format),
    logbook.StreamHandler(sys.stdout, level=logbook.ERROR, format_string=log_format),
    #logbook.StreamHandler(sys.stderr, level=logbook.ERROR, format_string=log_format),
])
zipline_logging.push_application()
log = logbook.Logger('AlgoLogger')


#from pytz    import timezone as tz
def minut(context): #Minute of trading day
    dt = context.get_datetime().astimezone(pytz.timezone('US/Eastern'))
    return (dt.hour * 60) + dt.minute - 570

import sys, os, inspect
from pathlib import Path

def get_script_dir(follow_symlinks=True):
    if getattr(sys, 'frozen', False): # py2exe, PyInstaller, cx_Freeze
        path = os.path.abspath(sys.executable)
    else:
        path = inspect.getabsfile(get_script_dir)
    if follow_symlinks:
        path = os.path.realpath(path)
    return os.path.dirname(path)

path = get_script_dir()

# aws_ec2
from os import getenv
HCA_RELEASE_STRAT_DIR = getenv("HCA_RELEASE_STRAT_DIR", path)
sys.path.append(os.path.abspath(HCA_RELEASE_STRAT_DIR))
LOCAL_ZL_LIVE_PATH = HCA_RELEASE_STRAT_DIR #Set up local execution path
sys.path.append(os.path.abspath(LOCAL_ZL_LIVE_PATH))
print ("Added to sys.path: LOCAL_ZL_LIVE_PATH = {}".format(LOCAL_ZL_LIVE_PATH))

import pprint as pp
def print_positions(ord_sid_dict):
    pp.pprint(dict([(k.symbol,v.amount) for k,v in ord_sid_dict.items()]), indent=4)

def update_portfolio_auto_close(context, data):
    c = context
    for s in c.auto_close:           # Log auto close value etc when it happened
        if s not in c.portfolio.positions:
            value = c.auto_close[s]['price'] * c.auto_close[s]['amount']
            log.info('InACnotPort:{}  prc {}  amt {}  value {}  end {}  auto close {}'.format(
            s.symbol, c.auto_close[s]['price'], c.auto_close[s]['amount'],
            value, s.end_date.date(), s.auto_close_date.date()))

    c.auto_close = {}
    for s in c.portfolio.positions:  # Store info when auto close approaches within ac_th=5 days(one-week)
        if (s.auto_close_date - c.get_datetime()).days > 5: continue
        price = 0   # somersaults to try to capture a recent valid price
        prc = data.current(s, 'price')
        if prc and prc == prc:  # avoid 0 and trick to avoid nan
            price = prc
        else:
            prc = c.portfolio.positions[s].last_sale_price
            if prc and prc == prc: price = prc
            else:
                prc = data.history(s, 'price', 1, '1d')[-1]
                if prc and prc == prc:
                    price = prc
        # keep previously stored price if 0 this time
        if price == 0 and s in c.auto_close: price = c.auto_close[s]['price']
        c.auto_close[s] = {
          'price' : price,
          'amount': c.portfolio.positions[s].amount,
        }
    print("InAC: CurDate={} context.auto_close={}".format(c.get_datetime(), c.auto_close))
    
    
def prorate(dist, max_alloc=0.1, atol=1.e-3):
    if (dist is None) or (len(dist) == 0):  #Pass on empty dist
        return dist
    cur_pr  = np.ma.array(dist)
    anymore = cur_pr[cur_pr>=max_alloc].count()
    while(anymore > 0):
        dist_m           = cur_pr
        redist           = (dist_m[cur_pr>=max_alloc]).sum() - (max_alloc)*len(dist_m[dist_m>=max_alloc])
        prd_mask         = np.ma.greater_equal(dist_m, max_alloc)
        prd              = np.ma.array(dist_m, mask = prd_mask)
        prd_norm         = prd/prd.sum()
        delta_redistrib  = redist*prd_norm
        cur_pr           = delta_redistrib + prd
        anymore = (cur_pr[cur_pr>=max_alloc]).count()
        #cur_pr[cur_pr >=max_alloc] = ma.masked

    final_pr = cur_pr.data
    final_pr[cur_pr.mask] =  max_alloc
    zero_msk=np.isclose(final_pr,0, atol=atol)
    final_pr[zero_msk] = 0
    #final_pr[final_pr>=max_alloc] = max_alloc
    final_normed = final_pr
    if abs(final_normed.sum()) > 0:
        final_normed = final_pr/final_normed.sum()
    print("prorate: len={} sum={}".format(len(final_normed), final_normed.sum()))
    return final_normed
    #wts_pr = prorate(allocation, max_alloc= 2.0 * context.maxportfoliobin)  put this somewhere

def initialize(context):
    attach_pipeline(make_pipeline(), 'pipeline')
    #Schedule Functions
    if not IS_LIVE:
        schedule_function(
            trade,
            #date_rules.every_day(),
            #date_rules.week_end(days_offset=1),#0=Fri 1= Thurs
            date_rules.month_end(days_offset=3),
            time_rules.market_close(minutes=30)
        )
        schedule_function(record_vars, date_rules.every_day(), time_rules.market_close())
        schedule_function(cancel_open_orders, date_rules.week_end(days_offset=2), time_rules.market_close())
    
    context.spy = symbol('SPY')  #sid(8554) #SPY
    context.TF_filter = False
    #context.TF_lookback = 60
    #Set number of securities to buy and bonds fund (when we are out of stocks)
    context.Target_securities_to_buy = 15 #10 #15 #2 #1 #5 #10 #5
    
    context.bonds = symbol('IEF') #sid(23870)  #IEF
    context.relative_momentum_lookback = 44 #66 #22 #4 #22 #22 #22 #126 #Momentum lookback
    context.momentum_skip_days = 1
    context.top_n_relative_momentum_to_buy = 10 #15 #10 #15 #1 #5 #5 #10 #5 #Number to buy
    context.stock_weights = pd.Series()
    context.bond_weights = pd.Series()

    context.auto_close = {} #Initialize portfolio auto_close list.
    context.TRACK_ORDERS_ON = False

def before_trading_start(context, data):
    c = context
    update_portfolio_auto_close(c, data)

    c.ORDERS_DONE       = False #No Orders done yet today
    c.REBALANCE_DONE    = False #No Orders done yet today
    c.MINUTES_TO_REBAL  = MINUTES_TO_REBAL

    c.all_orders = {}
    ### ajjc live
    if IS_LIVE:
        #schedule_function(rebalance, date_rules.every_day(),time_rule=time_rules.market_open())
        #schedule_function(rebalance, date_rules.every_day(),time_rule=time_rules.every_minute())
        for i in range(1, 391):
            #Daily schedule_function(rebalance, date_rules.every_day(), time_rules.market_open(minutes=i))
            #Weekley
            schedule_function(func=rebalance,
                             date_rule=date_rules.every_day(),
                             time_rule=time_rules.market_open(minutes=i),
                             half_days=True)
        pass
    current_time = context.get_datetime('US/Eastern')
    if DEBUG:
        log.debug( 'Time:before_trading_start:US/Eastern {}'.format(current_time ))

    df_pre = pipeline_output('pipeline')
    if not df_pre.empty:  # Drop Sharadar assets with '.' or '-' in the symbol, as IB does not support that naming.
        df_pre = df_pre.reset_index()
        num_full_assets = len(df_pre)
        df_pre = df_pre[df_pre['index'].map(lambda x:len(str(x.symbol).split('.')) == 1)].set_index('index')
        #df_pre = df_pre[df_pre['index'].map(lambda x:len(str(x.symbol).split('-')) == 1)].set_index('index')
        print("NumAssetsDropped={}".format(num_full_assets - len(df_pre)))
        
        # Filter out incompatible assets (extend this later via FIGGY mappings)
        ##Remove rows with assets that have - or . in symbol name, as they are wrong IB symbol name formats.
        ##Remove rows with assets that have exchange=1, as those are from SF1(Funds/ETFs/Indexes)
        for row in df_pre.index:
            if (row.symbol.split('-')[0] == row.symbol) and (row.symbol.split('.')[0] == row.symbol) and (row.exchange=='0'):
                print("Keep Asset:{} exchange:{}".format(row, row.exchange))
            else:
                print("Remove Asset:{} exchange:{}".format(row, row.exchange))
                df_pre.drop(row, inplace=True)
        
    c.pipeline_data = df_pre


    if len(c.auto_close) >0:
        for x in c.auto_close:
            if x in c.pipeline_data:
                c.pipeline_data.drop(x, inplace=True)
                print("DroppedFromPipeline:InAutoClose:[{}] Date:{}".format(x, c.get_datetime()))
    
    print("BeforeTrStrt:", c.pipeline_data)
    
    # ajjc Test Using broker=IB + data-frequncy=daily:
    #spy_maFast_curr = data.current(symbol('AAPL') , "price")
    #spy_maFast = data.history(symbol('AAPL') , "price", 5, "1d")
    #print("spy_maFast",spy_maFast)
    
    log.info("BTS___CurrZiplinPosBef: {}".format(context.portfolio.positions)) #BUG: This is a Criticalupdate...
    if IS_LIVE:
        log.info("BTS___CurrBrokerPosCur: {}".format(context.broker.positions))
    for x in list(context.portfolio.positions):
        #ajjc: zlb: BUG: Clean out null portfolio values. Handle this generically in zipline-broker in some way
        amt_x_port = context.portfolio.positions[x].amount
        if amt_x_port == 0:
            del context.portfolio.positions[x]
    log.info("BTS___CurrZiplinPosAft: {}".format(context.portfolio.positions)) #BUG: This is a Criticalupdate...

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
        
def handle_data(context, data):
    time_now = minut(context)
    log.info("___handle_data: {} = Current Trading Minute".format(time_now))
    sync_portfolio_to_broker(context, data)


# Average Dollar Volume without nanmean, so that recent IPOs are truly removed
class ADV_adj(CustomFactor):
    inputs = [USEP.close, USEP.volume]
    window_length = 252

    def compute(self, today, assets, out, close, volume):
        close[np.isnan(close)] = 0
        out[:] = np.mean(close * volume, 0)


NUM_TOP_INDEBTED = 15 #10 #20



def universe_filters():

    # Equities with an average daily volume greater than 750000.
    high_volume = AverageDollarVolume(window_length=66) > 1500000

    # Equities for which morningstar's most recent Market Cap value is above $300

    # Equities whose exchange id does not start with OTC (Over The Counter).
    # startswith() is a new method available only on string-dtype Classifiers.
    # It returns a Filter.
    #not_otc = ~mstar.share_class_reference.exchange_id.latest.startswith('OTC')

    # Equities whose symbol (according to morningstar) ends with .WI
    # This generally indicates a "When Issued" offering.
    # endswith() works similarly to startswith().
    #not_wi = ~mstar.share_class_reference.symbol.latest.endswith('.WI')

    # Equities whose company name ends with 'LP' or a similar string.
    # The .matches() method uses the standard library `re` module to match
    # against a regular expression.
    #not_lp_name = ~mstar.company_reference.standard_name.latest.matches('.* L[\\. ]?P\.?$')

    # Equities with a null entry for the balance_sheet.limited_partnership field.
    # This is an alternative way of checking for LPs.
    #not_lp_balance_sheet = mstar.balance_sheet.limited_partnership.latest.isnull()

    # Highly liquid assets only. Also eliminates IPOs in the past 12 months
    # Use new average dollar volume so that unrecorded days are given value 0
    # and not skipped over
    # S&P Criterion

    #liquid = ADV_adj()
    #liq_f = liquid > 25000
    # Add logic when global markets supported
    # S&P Criterion
    #domicile = True

    #universe_filter = (high_volume & primary_share & have_market_cap & not_depositary &
    #                   common_stock & not_otc & not_wi & not_lp_name & not_lp_balance_sheet &
    #                  liquid & domicile)
    #universe_filter = (high_volume & liq_f)
    universe_filter = (high_volume)


    return universe_filter

def make_pipeline():
    # Base universe set to the Q500US
    universe = universe_filters() # Q3000US()
        # Create the factors we want use
    #rsi = RSI()
    price_close = USEP.close.latest
    fd=Fundamentals()
    price_volm = USEP.volume.latest
    mc   = fd.marketcap
    de   = fd.de
    dnc  = fd.debtnc
    eusd = fd.equityusd
    fcf = fd.fcf
    # Create a filter to select our 'universe'
    # Our universe is made up of stocks that have a non-null sentiment signal that was updated in
    # the last day, are not within 2 days of an earnings announcement, are not announced acquisition
    # targets, and are in the Q1500US.

    ltd_to_eq_rank = np.divide(dnc.latest, eusd.latest) #Fundamentals.long_term_debt_equity_ratio.latest
    # Create a screen for our Pipeline
    #adv5000 = AverageDollarVolume(window_length = 44).percentile_between(90,100)
    #mcap3000 = mc.latest.percentile_between(90,100) 
    #universe = universe & adv5000 & mcap3000


    adv5000 = AverageDollarVolume(window_length = 30).top(1500)
    mcap3000 = mc.latest.top(500)

    universe =  universe & adv5000 & mcap3000

    universe = universe & (fcf.latest > 1.5e8) & (mc.latest >25e6) & (price_close > 10.0) & (price_volm > 1500000) & (ltd_to_eq_rank < 32.0) #100000 is too big #10000 is too small. Cannot get subscription for ILTB

    de_f = de.latest #Fundamentals.long_term_debt_equity_ratio.latest
    #print(dir(universe))
    #universe=~universe.matches('.*[-]*$')

    indebted = ltd_to_eq_rank.top(NUM_TOP_INDEBTED, mask=universe) #10 30 150 60

    dnc_f = dnc.latest
    eusd_f = eusd.latest
    fcf_f = fcf.latest

    #mom    = Returns(inputs=[USEP.open],window_length=126,mask=indebted)
    #mom_av = SimpleMovingAverage(inputs=[mom],window_length=22,mask=indebted)

    pipe = Pipeline(columns={
        'close':price_close,
        'volm' :price_volm,
        'ltd_to_eq_rank': ltd_to_eq_rank,
        'de'  : de_f,
        'dnc' : dnc_f,
        'eusd': eusd_f,
        'fcf': fcf_f,
         'adv': adv5000,
        'mcap': mcap3000,
        #' mom' : mom,
        # 'mom_av': mom_av
        },
                    screen=indebted)
    return pipe

def minut(context): #Minute of trading day
    dt = context.get_datetime().astimezone(pytz.timezone('US/Eastern'))
    return (dt.hour * 60) + dt.minute - 570

def rebalance(context, data):

    # This will be run once in befor_trading_start, to get new portfolio distribution from the factor,
    # and every minute during the trading session.  It will only actually rebalance/order the portfolio ONCE during the trading day,
    #and return without doing anything otherwise
    #log.info('rebalance: num_trading_minutes = {} num_portfolio_assets = {}'.format(minut(context), len(list(context.portfolio.positions))))
    #log.debug("-------- all_orders={}".format(context.all_orders))
    time_now = minut(context)
    time_till_trade = time_now -context.MINUTES_TO_REBAL
    if np.isnan(context.portfolio.portfolio_value):
        portfolio_value = 0.0
    else:
        portfolio_value = context.portfolio.portfolio_value
    if DEBUG:
        log.info('rebalance_top: time_till_trade={} curr_min={} portval={}'.format(time_till_trade, time_now, int(portfolio_value)))

    if IS_LIVE:
        if (not context.ORDERS_DONE)  and (time_till_trade > 0) :
            log.info('IS_LIVE:{} execute trade(context, data): time_till_trade={} curr_min={} portval={}'.format(IS_LIVE, time_till_trade, time_now, int(portfolio_value)))
            context.ORDERS_DONE = True
            trade(context, data)

def trade(context, data):

    # Get daily pipeline output
    df = context.pipeline_data
    
    # Filter out incompatible assets (extend this later via FIGGY mappings)
    ##Remove rows with assets that have - or . in symbol name, as they are wrong IB symbol name formats.
    ##Remove rows with assets that have exchange=1, as those are from SF1(Funds/ETFs/Indexes)
    for row in df.index:
        if (row.symbol.split('-')[0] == row.symbol) and (row.symbol.split('.')[0] == row.symbol) and (row.exchange=='0'):
            print("trade: Keep Asset:{} exchange:{}".format(row, row.exchange))
        else:
            print("trade: Remove Asset:{} exchange:{}".format(row, row.exchange))
            df.drop(row, inplace=True)
            
    print(df.index)

    log.info("BeginTrade")
    if IS_LIVE:
        log.info("Update context.portfolio by calling broker.portfolio")
        log.info("trade:___CurrBrokerPosCur: {}".format(context.broker.positions))
         
    ############Trend Following Regime Filter############
    #CrossOver_Fast_Slow_Pair = (5, 20)
    CrossOver_Fast_Slow_Pair = (10, 100)
    spy_maFast = data.history(context.spy , "close", CrossOver_Fast_Slow_Pair[0], "1d").mean()
    spy_maSlow = data.history(context.spy , "close", CrossOver_Fast_Slow_Pair[1], "1d").mean()
    log.info("SPY_MA_CROSS:{}:spy_maFast= {} :spy_maSlow = {}".format(spy_maFast >= spy_maSlow, spy_maFast, spy_maSlow))

    if spy_maFast >= spy_maSlow: #actual
        context.TF_filter = True
    else:
        context.TF_filter = False

    #DataFrame of Prices for our 500 stocks
    #Symbol hack:Removing all "-Px" postfixs involving preferred stocks
    #df.index = df.index.str.split('-').str[0]

    prices = data.history(df.index,"close", context.relative_momentum_lookback + 1, "1d") #180
    log.info("prices:\n{}\n".format( prices))

    #Calculate the momentum of our top ROE stocks
    quality_momentum = prices[:-context.momentum_skip_days].pct_change(context.relative_momentum_lookback - 1).iloc[-1]

    #Grab stocks with best momentum
    top_n_by_momentum = quality_momentum.nlargest(context.top_n_relative_momentum_to_buy)

    context.stock_weights = pd.Series(index=top_n_by_momentum.index , data=0.0)
    context.bond_weights = pd.Series(index=[context.bonds], data=0.0)
    #Update portfolio.positios from broker.portfolio
    if IS_LIVE:
        log.info("trade:___CurrBrokerPosCur: {}".format(context.broker.positions)) #BUG: This kicks off a re-read from IB-broker, and is a Criticalupdate...
        log.info("trade:___CurrPortfolioPosCur: {}".format(context.portfolio.positions)) #BUG: This kicks off a re-read from IB-broker, and is a Criticalupdate...
        
    for x in list(context.portfolio.positions):
        if (x in top_n_by_momentum) and (x.sid != context.bonds.sid) and (x not in context.auto_close) and (context.portfolio.positions[x].amount > 0):
            a=context.portfolio.positions[x].amount
            b=context.portfolio.positions[x].cost_basis #cost_basis != last_sale_price, if context.broker.portfolio not updated. It gives 0.0 here in live trading
            c=context.portfolio.starting_cash
            #c=context.portfolio.portfolio_value
            s_w= (a*b)/c
            #s_w = 0 if np.isclose(s_w, 0, atol=1.e-3) else s_w #1e-3= .001 = 0.1% --> clip port val to 0.
            if s_w <0:
                log.info("DUMP SHORT in current portfolio:[asset{}:amt{}] Date:{}".format(x, a, context.get_datetime()))
                order_target_percent(x, 0)
            else:
                context.stock_weights.set_value(x,s_w)
            log.info("CurrPosInTopMomentum::[asset{}:amt{}:pct_cur_port{}] Date:{}".format(x, a, s_w*100., context.get_datetime()))
            
        elif ((x not in top_n_by_momentum) and (x.sid != context.bonds.sid) and (x not in context.auto_close)) or (context.portfolio.positions[x].amount < 0):
            amt_x_port = context.portfolio.positions[x].amount
            log.info("DUMP LONG in curr_port, not in top_momentum: context.portfolio.positions[{}].amount is {}".format(x, amt_x_port))
            if amt_x_port == 0:
                del context.portfolio.positions[x]
            else:
                order_target_percent(x, 0)
                log.info("ORDER:ZERO: context.portfolio.positions[{}].amount is {}".format(x, amt_x_port))
    
    ###prorate(context.stock_weights, max_alloc=0.2, atol=1.e-3)
    #if abs(top_n_by_momentum.sum()) > 0:
        #mx = top_n_by_momentum.max(); mn = top_n_by_momentum.min()
        #context.stock_weights = (top_n_by_momentum - mn) / (mx - mn)
        #context.stock_weights = context.stock_weights/abs(context.stock_weights.sum())
    
    for x in top_n_by_momentum.index:
        if x not in context.portfolio.positions and context.TF_filter==True:
            context.stock_weights.set_value(x,1.0 / context.Target_securities_to_buy)
            
    wts_prated_array      = prorate(context.stock_weights, max_alloc=(1.0 / context.Target_securities_to_buy), atol=1.e-3)
    context.stock_weights = pd.Series(data=wts_prated_array, index=context.stock_weights.index)

    if context.stock_weights.sum()>1:
        stocks_norm=(1.00/context.stock_weights.sum())
        context.stock_weights=context.stock_weights*stocks_norm
        context.bond_weights.set_value(context.bonds,0.0)
    else:
        context.bond_weights.set_value(context.bonds,1-context.stock_weights.sum())

    total_weights = pd.concat([context.stock_weights, context.bond_weights])
    log.info("ORDER:: context.portfolio.positions: {}\n total_weights:\n{}".format(context.portfolio.positions, total_weights))

    for index, value in total_weights.iteritems():
        if (index in context.auto_close and (index.sid != context.bonds.sid)):
            log.info("DontBuy:InAutoClose:[{}] Date:{}".format(index, context.get_datetime()))
            if index in context.portfolio.positions:
                amt_x_port = context.portfolio.positions[index].amount
                log.info("CloseOut:InAutoClose-and-Portfolio:[{}]-[{}]-shares Date:{}".format(index, amt_x_port, context.get_datetime()))
                ###order_target_percent(index, 0)
        else:
            order_target_percent(index, value)

    valid_df_wts = [x for x in total_weights.index if ((x in df.index) and (x.sid != context.bonds))]
    #invalid_df_wts = set(list(total_weights.index)) -  set(valid_df_wts)
    invalid_df_wts = set(list(total_weights.index)) -  set(valid_df_wts + [context.bonds])
    log.info("InvalidPort:{} ValidPort:[{}]\n\n".format(invalid_df_wts, df.loc[valid_df_wts,:]))

    log.info("EndTrade")

def record_vars(context, data):
   record(leverage = context.account.leverage)
   longs = shorts = 0
   for position in context.portfolio.positions:
       pos_amt = context.portfolio.positions[position].amount
       if pos_amt > 0: longs += 1
       elif pos_amt < 0: shorts += 1
   record(long_count = longs, short_count = shorts, port_wts= context.stock_weights.sum())
   log.info("\nlongs={} shorts={} lvg={}\n".format(longs,shorts,context.account.leverage))
   log.info("PortfolioPositions:\n{}".format(print_positions(context.portfolio.positions)))
   if (shorts >0): # or (context.account.leverage >1.25):
       log.info("BAD: shorts={} lvg={}".format(shorts,context.account.leverage))
   if (longs < 2): # or (context.account.leverage >1.25):
       log.info("NO-ASSETS: longs={} lvg={}".format(longs,context.account.leverage))


def cancel_open_orders(self, data):
    for security in get_open_orders():
        for order in get_open_orders(security):
            cancel_order(order)
            log.warn('CANCEL: {} had open orders {}: now cancelled'.format(str(security),order))
