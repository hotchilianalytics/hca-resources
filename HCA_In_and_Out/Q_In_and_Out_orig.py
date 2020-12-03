# Vlad Code from: Aleksei Dremov  in
# https://www.quantopian.com/posts/live-slash-paper-trade-the-in-out-stragegy

# Price relative ratios (intersection) with wait days
import numpy as np
# -----------------------------------------------------------------------------------------------
STOCKS = symbols('QQQ'); BONDS = symbols('TLT','IEF'); LEV = 1.00; wt = {};
A = symbol('SLV'); B = symbol('GLD'); C = symbol('XLI'); D = symbol('XLU');
MKT = symbol('QQQ'); VOLA = 126; LB = 1.00; BULL = 1; COUNT = 0; OUT_DAY = 0; RET_INITIAL = 80;
# -----------------------------------------------------------------------------------------------
def initialize(context):
    schedule_function(daily_check, date_rules.every_day(), time_rules.market_open(minutes = 140))
    schedule_function(record_vars, date_rules.every_day(), time_rules.market_close())
def daily_check(context,data):
    global BULL, COUNT, OUT_DAY
    vola = data.history(MKT, 'price',  VOLA + 1, '1d').pct_change().std() * np.sqrt(252)
    WAIT_DAYS = int(vola * RET_INITIAL)
    RET = int((1.0 - vola) * RET_INITIAL)
    P = data.history([A,B,C,D], 'price',  RET + 2, '1d').iloc[:-1].dropna()
    ratio_ab = (P[A].iloc[-1] / P[A].iloc[0]) / (P[B].iloc[-1] / P[B].iloc[0])
    ratio_cd = (P[C].iloc[-1] / P[C].iloc[0]) / (P[D].iloc[-1] / P[D].iloc[0])
    exit = ratio_ab < LB and ratio_cd < LB
    if exit: BULL = 0; OUT_DAY = COUNT;
    elif (COUNT >= OUT_DAY + WAIT_DAYS): BULL = 1
    COUNT += 1
    wt_stk = LEV if BULL else 0;
    wt_bnd = 0 if BULL else LEV;
    for sec in STOCKS: wt[sec] = wt_stk / len(STOCKS);
    for sec in BONDS: wt[sec] = wt_bnd / len(BONDS)

    for sec, weight in wt.items():
        order_target_percent(sec, weight)
    record( wt_bnd = wt_bnd, wt_stk = wt_stk )

def record_vars(context, data):
    record(leverage = context.account.leverage)