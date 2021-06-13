# Vlad Code from: Aleksei Dremov  in
# https://www.quantopian.com/posts/live-slash-paper-trade-the-in-out-stragegy

# Price relative ratios (intersection) with wait days
import numpy as np

from zipline.api import order, cancel_order, get_open_orders, symbol, symbols, date_rules, time_rules, order_target_percent, record, schedule_function, get_datetime
from trading_calendars import get_calendar

def initialize(context):
    # -----------------------------------------------------------------------------------------------
    c = context
    c.STOCKS = symbols('QQQ', 'WCLD'); c.BONDS = symbols('TLT','IEF', 'SCHD'); c.LEV = 1.00; c.wt = {};
    c.A = symbol('SLV'); c.B = symbol('GLD'); c.C = symbol('XLI'); c.D = symbol('XLU');
    c.MKT = symbol('QQQ'); c.VOLA = 126; c.LB = 1.00; c.BULL = 1; c.COUNT = 0; c.OUT_DAY = 0; c.RET_INITIAL = 80;
# -----------------------------------------------------------------------------------------------

    schedule_function(daily_check, date_rules.every_month(), time_rules.market_open(minutes = 140))
    #schedule_function(daily_check, date_rules.every_day(), time_rules.market_open(minutes = 140))
    schedule_function(record_vars, date_rules.every_day(), time_rules.market_close())
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

    for sec, weight in c.wt.items():
        order_target_percent(sec, weight)
    record( wt_bnd = wt_bnd, wt_stk = wt_stk )

def record_vars(context, data):
    record(leverage = context.account.leverage)