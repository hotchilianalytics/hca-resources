# Modifications:HotChili Analytics - Copyright (c) 2021

# https://github.com/neptune-ai/neptune-contrib/tree/master/neptunecontrib/bots
# Copyright (c) 2019, Neptune Labs Sp. z o.o.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ----------------------------------------------
# Date: 2021-03-21
# Author: ajjcoppola@hotchilianalytics.com
# This file used as a template, for OO techniques of handling a python-telegram-bot.

# Date: 2021-04-18
# Author: ajjcoppola@hotchilianalytics.com
# Notes: Create demo telegram bot for HCA algo.  SUpport /plot and /sig with only defaults.

"""Spins of a bot with which you can interact with on telegram

You can see which stats are running, check the best experiements based
on defined metric and even plot it in Telegram.

Full list of options:
 * /help (/h) 
 * /plot (/p) stk_sym
 * /sig  (/s)  days
 

Attributes:
    telegram_api_token(str): Your telegram bot api token.
        You can pass it either as --telegram_api_token or -t.

Example:
    Spin off your bot::

        $ python -m hca_bot
            --telegram_api_token 'a1249auscvas0vbia0fias0'
            --list_hca_strats

    Go to your telegram and type.

    
    `/start`
    '/help (/h)'

    Use help to see what is implemented.

     * '/plot help' or '/p h'
     * '/sig help'  or '/s h'
     * '/help'

"""

import argparse
from io import BytesIO

import sys
from io import StringIO

#from neptune.sessions import Session
import matplotlib.pyplot as plt
import pandas as pd
from telegram.ext import Updater
from telegram.ext import CommandHandler, MessageHandler, Filters

import numpy as np
import pyfolio as pf
import ffn

HCA_Namespaces = ['hca']
HCA_Strategies = ['MeanRevZ', 'DebtEqRatio']
HCA_Equity     = 'SPY' 
import hca_mrevonez as mr

class ListStream: #ContextManager for StringIO, to support print() 
    def __init__(self):
        self.data = StringIO()
    def write(self, s):
        self.data.write(s)
    def __enter__(self):
        sys.stdout = self
        return self
    def __exit__(self, ext_type, exc_value, traceback):
        sys.stdout = sys.__stdout__ 
        
class TelegramBot:
    def __init__(self, telegram_api_token):
        self.updater    = Updater(token=telegram_api_token, use_context=False)
        self.dispatcher = self.updater.dispatcher
        self.namespaces = HCA_Namespaces
        self.strategies = HCA_Strategies
        self.strat_name = HCA_Strategies[0] # Default: Take the first strat in list.
        self.equity     = HCA_Equity #default
        self.is_binary  = True  # Output buy/hold/sell signal as True=1/0/-1, False=buy/hold/sell num_shares=tot_money/price_per_share.
        self.capital    = 10000.0
        self.tail_days  = 22   # Default: 1 month tail days = 22
        self.sim_days  = 2*365 # Default: simulation days = 2 years = 2*365 days
        self.detail_days = 0 # Default: output 0 days of detail.
        
        self.dispatcher.add_handler(CommandHandler('sig', self.sig, pass_args=True))
        self.dispatcher.add_handler(CommandHandler('s', self.sig, pass_args=True))
        self.dispatcher.add_handler(CommandHandler('plot', self.plot, pass_args=True))
        self.dispatcher.add_handler(CommandHandler('p', self.plot, pass_args=True))
        self.dispatcher.add_handler(MessageHandler(Filters.command, self.unknown))

    def run(self):
        self.updater.start_polling()
        self.updater.idle()


    def sig(self, bot, update, args):
        if len(args) < 3:
            self._sig(bot, update, args) #/sig <asset> <days>
        else:
            self._help(bot, update)
    def s(self, bot, update, args):
        if len(args) < 3:
            self._sig(bot, update, args) #/s <asset> <days>
        else:
            self._help(bot, update)

    def plot(self, bot, update, args):  #/plot <asset>
        if len(args) < 2:
            self._sig2(bot, update, args)
            self._plot(bot, update, args)
        else:
            self._help(bot, update)
    def p(self, bot, update, args):  #/p <asset>
        if len(args) < 2:
            self._sig2(bot, update, args)
            self._plot(bot, update, args)
        else:
            self._help(bot, update)

    def unknown(self, bot, update):
        bot.send_message(chat_id=update.effective_chat.id,
                         text="Sorry, I only undestand , /plot (/p) or /sig (/s)")

                    
    # /sig <asset_name> <num_days> 
    def _sig2(self, bot, update, args):
        if len(args) < 3:
             
            if len(args) == 1:
                if str(args[0]).isalpha():
                    self.equity = str(args[0]).upper()
                elif str(args[0]).isdigit():
                    self.tail_days = int(args[0])
            if len(args) == 2:
                if str(args[0]).isalpha():
                    self.equity = str(args[0]).upper()
                elif str(args[0]).isdigit():
                    self.tail_days = int(args[0])
                    
                if str(args[1]).isalpha():
                    self.equity = str(args[1]).upper()
                elif str(args[1]).isdigit():
                    self.tail_days = int(args[1])
                    
            try:
                
                end_dt  = pd.datetime.today()
                strt_dt = end_dt - pd.DateOffset(days=self.sim_days)                    
                strt_ts =  strt_dt.strftime("%Y-%m-%d")
                end_ts  = end_dt.strftime("%Y-%m-%d")
                print("start={} end={} simdays={} tail_days={} len(args)={}  args={}".format(strt_ts, end_ts, self.sim_days, self.tail_days, len(args), args))
                                        
                msg     = ['Using equity ',
                           self.equity,
                           'with strategy:',
                           self.strat_name,
                           'during period:',
                           '['+ strt_ts + ', ' + end_ts +']'
                           ]
    
                self.strat = mr.MeanRevOneSymZ(strt_ts, end_ts)
                self.strat.asset_sym = self.equity
                self.strat.capital = self.capital
                
                stock      = self.strat.get_asset_data(self.strat.av_key, self.strat.asset_sym, strt_ts, end_ts)
    
                bt_df      = self.strat.mr_trade(stock, self.strat.window_len)
                
                perf       = bt_df['equity'].calc_stats()
                
                perf_ret = pd.Series(bt_df['equity'])
                perf_ret = perf_ret.replace([np.inf, -np.inf], np.nan)
                perf_ret = perf_ret.fillna(0).diff().fillna(0)
                #.fillna(0).pct_change()
                
                #perf = pf.plotting.show_perf_stats(perf_ret, factor_returns=None, live_start_date=None)                
                #perf = pf.create_returns_tear_sheet(bt_df['equity'])
                
                with ListStream() as stats_msg: # contextmanager to re-direct print-sysout to StringIO instance.
                    perf.display()
                    #pf.plotting.show_perf_stats(perf_ret, factor_returns=None, live_start_date=None)
                
                stats_msg_list = stats_msg.data.getvalue().splitlines()
                
                #perf_equity_md = perf.stats.as_format('.3f').to_markdown()
                stats_disp =""
                if self.detail_days >0:
                    stats_disp_td = bt_df[['Close','money','amount','equity']]
                    stats_disp_td         = stats_disp_td.tail(self.detail_days).sort_index(axis=0, ascending=False)
                    msg2               = stats_disp_td.to_string(index_names=True,justify='right')
                    msg2               = '```\n' + msg2 +  '```\n' #markdown pre-formatted
                    
                    
                msg = '\n'.join(msg)
                stats_msg_str = '\n'.join(stats_msg_list)
                #stats_render_md = self.strat.stats_calc(bt_df)
                #msg = msg + "\n" + stats_render_md + "\n" + perf_equity_md
                #msg = msg + "\n" + stats_render_md + "\n" + stats_msg_str
                msg1 = '```\n' + msg + "\n" + stats_msg_str + '```\n' 
                msg2 = '```\n' + f"\n\nLast {self.tail_days} of strategy\n\n" +  '```\n'
    
                #bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='html')
                bot.send_message(chat_id=update.effective_chat.id, text=msg1, parse_mode='MarkdownV2')
                if self.detail_days >0:
                    bot.send_message(chat_id=update.effective_chat.id, text=msg2, parse_mode='MarkdownV2')
            except Exception as exception:
                msg = ["Exception: {}".format(type(exception).__name__),
                       "Exception message: {}".format(exception),         
                       'Bot data error with command /p ', 
                        "{}".format(args) ]
                msg = '\n'.join(msg)
                bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='html')
                
        else:
            bot.send_message(chat_id=update.effective_chat.id, text="Command /plot {} is invalid.".format(args))
    
        

    def _sig(self, bot, update, args):
        if len(args) < 3:
             
            if len(args) == 1:
                if str(args[0]).isalpha():
                    self.equity = str(args[0]).upper()
                elif str(args[0]).isdigit():
                    self.tail_days = int(args[0])
            if len(args) == 2:
                if str(args[0]).isalpha():
                    self.equity = str(args[0]).upper()
                elif str(args[0]).isdigit():
                    self.tail_days = int(args[0])
                    
                if str(args[1]).isalpha():
                    self.equity = str(args[1]).upper()
                elif str(args[1]).isdigit():
                    self.tail_days = int(args[1])
             
        try:            
            # /sig <asset_name> <num_days>             
            end_dt  = pd.datetime.today()
            strt_dt = end_dt - pd.DateOffset(days=self.sim_days)                    
            strt_ts =  strt_dt.strftime("%Y-%m-%d")
            end_ts  = end_dt.strftime("%Y-%m-%d")
            print("sig: start={} end={} sim_days={}  tail_days={} len(args)={}  args={}".format(strt_ts, end_ts, self.sim_days, self.tail_days, len(args), args))
                                    
            msg1    = ['Using stock ',
                       self.equity,
                       'with strategy: ',
                       self.strat_name,
                       ' during period: ',
                       '['+ strt_ts + ', ' + end_ts +']',
                       'producing CUR/TARG/SIG (+=BUY -=SELL 0=HOLD)',
                       'for last ',
                       str(self.tail_days),
                       ' days.',
                       '\n'
                       ]
            msg1 = '\n'.join(msg1)

            self.strat = mr.MeanRevOneSymZ(strt_ts, end_ts)
            self.strat.asset_sym = self.equity
            
            stock      = self.strat.get_asset_data(self.strat.av_key, self.strat.asset_sym, strt_ts, end_ts)
            bt_df      = self.strat.mr_trade(stock, self.strat.window_len)
            stats_disp = bt_df[['amount']]
            stats_disp['cur'] = stats_disp['amount'].shift(1)
            stats_disp['sig'] = stats_disp['amount'].diff()
            
            stats_disp.columns = ['targ','cur','sig'] #rename cols
            stats_disp         = stats_disp[['cur','targ','sig']].fillna(0) #reorder cols
            stats_disp         = stats_disp.tail(self.tail_days).sort_index(axis=0, ascending=False)
            if self.is_binary:
                stats_disp[stats_disp < 0] = -1
                stats_disp[stats_disp > 0] = 1
                #no behaviour defined for df = 0
                
            msg2               = stats_disp.to_string(index_names=True,justify='right')
            msg2               = '```\n' + msg2 +  '```\n' #markdown pre-formatted
            #msg2               = stats_disp.to_string(index_names=False, justify='right')
            #msg2= f"\n\nLast {sig_days} of strategy\n\n" + stats_disp.to_markdown() #needs pandas>=1.0
            
            bot.send_message(chat_id=update.effective_chat.id, text=msg1, parse_mode='html')
            bot.send_message(chat_id=update.effective_chat.id, text=msg2, parse_mode='MarkdownV2')
        except Exception as exception:
            msg = ["Exception: {}".format(type(exception).__name__),
                   "Exception message: {}".format(exception) ]          
            msg = msg + ['bot command format:',
                   '/sig STK and/or DAYS  (defaults: DAYS=22, EQUITY=spy)',  
                   'Signal Value= 1/0/-1 = Buy/Hold/Sell',  
                   'for example:',
                   '/sig',
                   '/s schd',
                   '/sig 22  (last 22 days of this trading signal)',
                   '/sig arkk 22 (last 22 days of the arkk  trading signal)']
            msg = '\n'.join(msg)
            bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='html')
            
            
    # /plot <asset_name> 
    def _plot(self, bot, update, args):
        if len(args) > 1:
            msg = ['Plot strategy CumulativeReturns chart:',
                   '/plot (/p) STK (Default: STK = spy, Compare last 2-yrs cumulative returns))',
                   '/p (Plot last 2 years of CumRets of current STK and Algo results.)' ,
                   'for example:',
                   '/plot ',
                   '/plot schd',
                    '/p zm',
                    '/plot  ief (Plot IEF CumReturn: Close vs. Algo']
            msg = '\n'.join(msg)
            bot.send_message(chat_id=update.effective_chat.id, text=msg)
        else:
            try:
                
                if len(args) == 0:
                    pass
                if len(args) == 1:
                    if str(args[0]).isalpha():
                        self.equity = str(args[0]).upper()
                    else:
                        bot.send_message(chat_id=update.effective_chat.id, text=f"Bad argument: /plot  {args}") 
    
                end_dt  = pd.datetime.today()
                strt_dt = end_dt - pd.DateOffset(days=self.sim_days)                    
                strt_ts =  strt_dt.strftime("%Y-%m-%d")
                end_ts  = end_dt.strftime("%Y-%m-%d")
                print("/plot: start={} end={} simdays={} len(args)={}  args={}".format(strt_ts, end_ts, self.sim_days, len(args), args))
                                        
                msg     = ['Using equity ',
                           self.equity,
                           'with strategy:',
                           self.strat_name,
                           'during period:',
                           '['+ strt_ts + ', ' + end_ts +']'
                           ]
    
                self.strat           = mr.MeanRevOneSymZ(strt_ts, end_ts)
                self.strat.asset_sym = self.equity
                self.strat.money     = self.capital
                
                stock      = self.strat.get_asset_data(self.strat.av_key, self.strat.asset_sym, strt_ts, end_ts)
                bt_df      = self.strat.mr_trade(stock, self.strat.window_len)
                
                fig        = plt.figure()
     
                #bt_df = bt_df.rename(columns={'equity': self.strat.asset_sym})
                bt_df['MeanRev-'+self.strat.asset_sym] = (bt_df[['equity']].pct_change()+1.).cumprod()
                bt_df['Close-'+self.strat.asset_sym] = (bt_df[['Close']].pct_change()+1.).cumprod()
                
                for channel_name in ['MeanRev-'+self.strat.asset_sym, 'Close-'+self.strat.asset_sym]:
                    plt.plot(channel_name, data=bt_df,
                         marker='', linewidth=2, label=channel_name)
                fig.autofmt_xdate()         
                plt.legend()
    
                buffer = BytesIO()
                fig.savefig(buffer, format='png')
                buffer.seek(0)
                update.message.reply_photo(buffer)
            except Exception as exception:
                msg = ["Exception: {}".format(type(exception).__name__),
                       "Exception message: {}".format(exception) ]          
                msg = msg + ['bot command format:',
                             'Plot strategy CumulativeReturns chart:',
                             '/plot (/p) STK (Default: STK = spy, Compare last 2-yrs cumulative returns))',
                             '/p (Plot last 2 years of CumRets of current STK and Algo results.)' ,
                             'for example:',
                             '/plot ',
                             '/plot schd',
                             '/p zm',
                             '/plot  ief (Plot IEF CumReturn: Close vs. Algo']
                msg = '\n'.join(msg)
                bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='html')

    def _help(self, bot, update):
        msg = """Available options are:\n
        /plot options
        /sig  options
        
        /plot ASSET,
                   for example (All parameters are sticky, and defaults are ASSET=spy, NUM_OF_DAYS=22):,
                   /plot       (Current values of ASSET and NUM_OF_DAYS)',
                   /plot zm
                   /p schd
                   
                   
        /sig ASSET NUM_OF_DAYS
                   for example (All parameters are sticky, and defaults are ASSET=spy, NUM_OF_DAYS=22):,
                   /sig,
                   /sig zm 100
                   /s schd
          """
        bot.send_message(chat_id=update.effective_chat.id, text=msg)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--telegram_api_token')
    #parser.add_argument('-l', '--list_hca_strats', default=None)
    return parser.parse_args()


if __name__ == '__main__':
    arguments = parse_args()
    telegram_bot = TelegramBot(telegram_api_token=arguments.telegram_api_token)  #,list_hca_strats=arguments.list_hca_strats)

    while True:
        telegram_bot.run()
        
