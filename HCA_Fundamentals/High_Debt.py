from zipline.pipeline.factors import AverageDollarVolume, SimpleMovingAverage, CustomFactor
from zipline.pipeline import Pipeline

from zipline.pipeline.data import USEquityPricing
from zipline.pipeline.data import USEquityPricing as USEP

from datetime import datetime
import pytz
from pytz import timezone as _tz  # Python only does once, makes this portable.
                    #   Move to top of algo for better efficiency.
#from zipline import run_algorithm
import pandas as pd
from zipline.api import (
    attach_pipeline,
    date_rules,
    order_target_percent,
    pipeline_output,
    record,
    schedule_function,
    set_benchmark,
    symbol,
    symbols
)

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

from zipline.finance import commission, slippage
from zipline.pipeline import Pipeline
from zipline.pipeline.factors import Returns, AverageDollarVolume

from alphatools.fundamentals import Fundamentals
fd = Fundamentals()

import numpy as np

#MOMENTUM_LOOKBACK = 126
#TOP_STOCKS = 60
TOP_LEVERAGE = 30
PFLIO_SZ = 20

def initialize(context):
    #set_benchmark(symbol('SPY'))
    #context.spy = symbol('SPY')  # sid(8554) #SPY
    context.TF_filter = False
    attach_pipeline(make_pipeline(), 'my_pipeline')
    schedule_function(
            rebalance,
            date_rules.every_day(),
            #date_rules.week_end(days_offset=1),#0=Fri 1= Thurs
            #date_rules.month_end(days_offset=3),
            time_rules.market_close(minutes=30)
        )

    #schedule_function(rebalance, date_rules.month_end())
    #context.set_commission(commission.PerShare(cost=.0075, min_trade_cost=1.0))
    #context.set_slippage(slippage.VolumeShareSlippage())

DomComStk_lst= [
        'Domestic Common Stock',
        'Domestic Common Stock Primary Class',
        'Canadian Common Stock',
        'Canadian Common Stock Primary Class',
        'ADR Common Stock',
        'ADR Common Stock Primary Class',
         #'Domestic Common Stock Secondary Class', 'Domestic Stock Warrant',
         #'Domestic Preferred Stock', 'ADR Stock Warrant',
         #'ADR Preferred Stock', 'ADR Common Stock Secondary Class',
         #'Canadian Stock Warrant', 'Canadian Preferred Stock', nan, 'ETF',
         #'CEF', 'ETN', 'ETD', 'IDX'
  ]  

def universe_filters():

        category = ~(fd.category.latest.eq("ADR Common Stock Secondary Class")| fd.category.latest.eq("ADR Preferred Stock")
                    | fd.category.latest.eq("ADR Stock Warrant") | fd.category.latest.eq("Canadian Preferred Stock") 
                    | fd.category.latest.eq("Canadian Stock Warrant") | fd.category.latest.eq("Domestic Common Stock Secondary Class")
                    | fd.category.latest.eq("Domestic Preferred Stock") |fd.category.latest.eq("Domestic Stock Warrant")  )
        category = category & (fd.category.latest.eq(DomComStk_lst[0]) 
                    | fd.category.latest.eq(DomComStk_lst[1])
                    | fd.category.latest.eq(DomComStk_lst[2])
                    | fd.category.latest.eq(DomComStk_lst[3])
                    | fd.category.latest.eq(DomComStk_lst[4])
                    | fd.category.latest.eq(DomComStk_lst[5])
                   )
                               
        exchange = ~fd.exchange.latest.startswith("OTC")
        ### notdelisted = fd.isdelisted.latest.eq('N')
        marketcap = fd.marketcap.latest.top(3000)
        high_volume = AverageDollarVolume(window_length=66) > 1500000

        ###orig high_volume = AverageDollarVolume(window_length=252) > 2000000
        price_volm_thres = USEP.volume.latest > 500000

        universe = (marketcap & high_volume &  price_volm_thres) #exchange  & category & notdelisted)
        debt = fd.debt.latest
        assets = fd.assets.latest
        universe_filter = np.divide(debt, assets).top(PFLIO_SZ, mask=universe) #20
        #universe_filter = universe 
        print("Being called.....")
        return universe_filter

def make_pipeline():
    universe = universe_filters()
    price_close = USEP.close.latest
    price_volm = USEP.volume.latest
    mc   = fd.marketcap.latest
    debt   = fd.debt.latest
    assets  = fd.assets.latest    
    #debt_to_assets_rank= np.divide(debt, assets).top(20,mask=universe)
    leverage = np.divide(debt, assets)
    #debt_to_assets_rank = np.divide(debt.latest, assets.latest)


    pipe = Pipeline(columns={
        #'category':fd.category.latest,
        #'close':price_close,
        'vol' :price_volm,
        #'debt_to_assets_rank': debt_to_assets_rank,
        'debt'  : debt,
        'assets' : assets,
        'mcap': mc,
        'leverage':leverage,
        },
                    screen=universe)
    return pipe

import pprint as pp
def before_trading_start(context, data):
    context.pipeline_data = pipeline_output('my_pipeline')
    pp.pprint(context.pipeline_data.head(PFLIO_SZ))

def rebalance(context, data):
    pipeline_data = context.pipeline_data
    all_assets = pipeline_data.index
    
    CrossOver_Fast_Slow_Pair = (10, 100)
    #spy_maFast = data.history(context.spy, "close", CrossOver_Fast_Slow_Pair[0], "1d").mean()
    #spy_maSlow = data.history(context.spy, "close", CrossOver_Fast_Slow_Pair[1], "1d").mean()
    # log.info("SPY_MA_CROSS:{}:spy_maFast= {} :spy_maSlow = {}".format(spy_maFast >= spy_maSlow, spy_maFast, spy_maSlow))

    #if spy_maFast >= spy_maSlow:  # actual
        #context.TF_filter = True
    #else:
        #context.TF_filter = False
    dt = context.get_datetime().astimezone(pytz.timezone('US/Eastern'))
    print("rebalance_date={} - universe_size={}".format(dt, len(all_assets)))
    for asset in all_assets:
        if data.can_trade(asset):  # and context.TF_filter == True:
            # if pipeline_data.momentum[asset]>0 and pipeline_data.stmomentum[asset]>0:
            order_target_percent(asset, 0.99 / PFLIO_SZ )
            print("{}".format(asset.symbol))
            #order_target_percent(asset, 0.95 / TOP_LEVERAGE )
        # else:
        # order_target_percent(asset, 0)

    # Remove any assets that should no longer be in our portfolio.
    positions = context.portfolio.positions
    # cut = viewkeys(positions) - set(all_assets)
    for asset in positions:
        if asset not in all_assets:
            # This will fail if the asset was removed from our portfolio because it
            # was delisted.
            if data.can_trade(asset):
                order_target_percent(asset, 0)