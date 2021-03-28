import numpy as np
import matplotlib.pyplot as plt
from matplotlib.pyplot import figure
import pandas as pd
from alpha_vantage.timeseries import TimeSeries
import fix_yahoo_finance as yf
#because the is_list_like is moved to pandas.api.types
pd.core.common.is_list_like = pd.api.types.is_list_like
import ffn
#import pixiedust



class MeanRevOneSymZ:
    def __init__(self, start_date, end_date, window_len=11, asset_sym='SPY', av_key='HK7Q1K6I2EIFKTVL'):
        self.window_len = window_len
        self.strt_date  = start_date
        self.end_date   = end_date
        self.av_key     = av_key
        self.asset_sym  = asset_sym

    def get_asset_data(self, av_key, asset_sym, strt_date, end_date):
        ts = TimeSeries(key=av_key, output_format='pandas')
        data, meta_data = ts.get_daily_adjusted(symbol=asset_sym, outputsize='full')
        data = yf.download(asset_sym, start=strt_date, end=end_date)
        data.rename(columns={'Adj Close': 'Adj_Close'}, inplace=True)
        data['Adj_Open']=data.Open*(data.Adj_Close/data.Close)
        data.to_csv(asset_sym + '.csv')    
        pricing = pd.read_csv(
            asset_sym + '.csv',
            header=0,
            parse_dates=["Date"],
            #index_col=0,
            usecols=['Date','Adj_Open', 'Adj_Close'])    
        stock=pricing.copy()
        stock.Adj_Close=stock.Adj_Close.shift(1)
        return stock
    
    
    # Trade using a simple mean-reversion strategy
    def mr_trade(self, stock, length):
        temp_dict = {}
        # If window length is 0, algorithm doesn't make sense, so exit
        if length == 0:
            return 0
    
        # Compute rolling means and rolling standard deviation
        #sma and lma are filters to prevent taking long or short positions against the longer term trend
        rolling_window = stock.Adj_Close.rolling(window=length)
        mu = rolling_window.mean()
        sma = stock.Adj_Close.rolling(window=length*1).mean()
        lma = stock.Adj_Close.rolling(window=length * 10).mean()
        std = rolling_window.std()
    
        #If you don't use a maximum position size the positions will keep on pyramidding.
        #Set max_position to a high number (1000?) to disable this parameter
        #Need to beware of unintended leverage
        max_position = 1
        percent_per_trade = 1.0
    
        #Slippage and commission adjustment  - simply reduces equity by a percentage guess
        # a setting of 1 means no slippage, a setting of 0.999 gives 0.1% slippage
        slippage_adj = 1
    
        # Compute the z-scores for each day using the historical data up to that day
        zscores = (stock.Adj_Close - mu) / std
    
        # Simulate trading
        # Start with your chosen starting capital and no positions
        money = 10000.00
        position_count = 0
    
        for i, row in enumerate(stock.itertuples(), 0):
    
            #set up position size so that each position is a fixed position of your account equity
            equity = money + (stock.Adj_Close[i] * position_count)
            if equity > 0:
                fixed_frac = (equity * percent_per_trade) / stock.Adj_Close[i]
            else:
                fixed_frac = 0
            fixed_frac = int(round(fixed_frac))
    
            #exit all positions if zscore flips from positive to negative or vice versa without going through
            #the neutral zone
            if i > 0:
                if (zscores[i - 1] > 0.5
                        and zscores[i] < -0.5) or (zscores[i - 1] < -0.5
                                                   and zscores[i] > 0.5):
    
                    if position_count > 0:
                        money += position_count * stock.Adj_Close[i] * slippage_adj
                    elif position_count < 0:
                        money += position_count * stock.Adj_Close[i] * (
                            1 / slippage_adj)
                    position_count = 0
    
            # Sell short if the z-score is > 1 and if the longer term trend is negative
            if (zscores[i] > 1) & (position_count > max_position * -1) & (sma[i] <
                                                                          lma[i]):
    
                position_count -= fixed_frac
                money += fixed_frac * stock.Adj_Close[i] * slippage_adj
    
            # Buy long if the z-score is < 1 and the longer term trend is positive
            elif zscores[i] < -1 and position_count < max_position and sma[i] > lma[i]:
    
                position_count += fixed_frac
                money -= fixed_frac * stock.Adj_Close[i] * (1 / slippage_adj)
    
            # Clear positions if the z-score between -.5 and .5
            elif abs(zscores[i]) < 0.5:
                #money += position_count * stock.Adj_Close[i]
                if position_count > 0:
                    money += position_count * stock.Adj_Close[i] * slippage_adj
                elif position_count < 0:
                    money += position_count * stock.Adj_Close[i] * (
                        1 / slippage_adj)
                position_count = 0
    
            #fill dictionary with the trading results.
            temp_dict[stock.Date[i]] = [
                stock.Adj_Open[i], stock.Adj_Close[i], mu[i], std[i], zscores[i],
                money, position_count, fixed_frac, sma[i], lma[i]
            ]
        #create a dataframe to return for use in calculating and charting the trading results
        pr = pd.DataFrame(data=temp_dict).T
        pr.index.name = 'Date'
        pr.index = pd.to_datetime(pr.index)
        pr.columns = [
            #'Open', 'Close', 'mu', 'std', 'zscores', 'money', 'position_count',
            'Open', 'Close', 'mu', 'std', 'zscores', 'money', 'amount',
            'fixed_frac', 'sma', 'lma'
        ]
        pr['equity'] = pr.money + (pr.Close * pr.amount)
        #pr['equity'] = pr.money + (pr.Close * pr.position_count)
        #
        return pr
    
    def stats_calc(self, profit):
        profit.to_csv('mean_reversion_profit.csv')
        profit            = profit.reset_index()
        profit_md         = profit[['Date','Close','amount','equity']].tail(22)
        profit_md['Date'] = [d.strftime('%y-%m-%d') if not pd.isnull(d) else '' for d in profit_md['Date']]        
        profit_md_render3 = profit_md.to_markdown(index=False)
        # Send a message with the stats
        #bot.send_message(chat_id=update.effective_chat.id, text=profit_md_render3, parse_mode='html')
        return profit_md_render3

