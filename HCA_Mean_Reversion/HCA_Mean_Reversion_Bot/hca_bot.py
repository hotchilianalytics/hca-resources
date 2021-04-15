# Modifications: HotChili Analytics - Copyright (c) 2021
# Date: 2021-03-22
# Author: ajjcoppola

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
# Author: ajjcoppola
# Modified this for HotChili Analytics usage.
# This file used as a template, for OO techniques of handling a python-telegram-bot.

"""Spins of a bot with which you can interact on telegram

You can see which stats are running, check the best experiements based
on defined metric and even plot it in Telegram.

Full list of options:
 * /strat list NAMESPACE
 * /strat select NAMESPACE/strat_NAME
 * /strat help
 
 * /stats last
 * /stats bt START_DATE END_DATE
 * /stats key NUM_KEY_STATS
 * /stats help
 
 * /cmd order STRAT_ID
 * /cmd plot STAT_NAME1 STAT_NAME2
 * /cmd help

Attributes:
    telegram_api_token(str): Your telegram bot api token.
        You can pass it either as --telegram_api_token or -t.

Example:
    Spin off your bot::

        $ python -m hca_bot
            --telegram_api_token 'a1249auscvas0vbia0fias0'
            --list_hca_strats

    Go to your telegram and type.

    `/strat list <hca|null>`

    Use help to see what is implemented.

     * '/strat help'
     * '/stats help'
     * '/cmd help'

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
        self.is_binary     = False  # Output buy/hold/sell signal as True=1/0/-1, False=buy/hold/sell shares
        self.capital    = 10000.0
        
        self.dispatcher.add_handler(CommandHandler('strat', self.strat, pass_args=True))
        self.dispatcher.add_handler(CommandHandler('stats', self.stats, pass_args=True))
        self.dispatcher.add_handler(CommandHandler('cmd', self.cmd, pass_args=True))
        self.dispatcher.add_handler(MessageHandler(Filters.command, self.unknown))

    def run(self):
        self.updater.start_polling()
        self.updater.idle()

    def strat(self, bot, update, args):
        if args:
            if args[0] == 'select':
                self._strat_select(bot, update, args)
            elif args[0] == 'list':
                self._strat_list(bot, update, args)
            else:
                self._strat_help(bot, update)
        else:
            self._strat_help(bot, update)

    def stats(self, bot, update, args):
        if not self.strat_name:
            self._no_strat_selected(bot, update)
        else:
            if args:
                if args[0] == 'latest':
                    self._stats_latest(bot, update, args)
                elif args[0] == 'bt':
                    self._stats_bt(bot, update, args)
                else:
                    self._stats_help(bot, update)
            else:
                self._stats_help(bot, update)

    def cmd(self, bot, update, args):
        if not self.strat_name:
            self._no_strat_selected(bot, update)
        else:
            if args:
                if args[0] == 'sig':
                    self._cmd_sig(bot, update, args)
                elif args[0] == 'plot':
                    self._cmd_plot(bot, update, args)
                else:
                    self._cmd_help(bot, update)
            else:
                self._cmd_help(bot, update)

    def unknown(self, bot, update):
        bot.send_message(chat_id=update.effective_chat.id,
                         text="Sorry, I only undestand /strat, /stats, /cmd")

    def _strat_list(self, bot, update, args):
        if len(args) != 2:
            msg = ['Listing all strategies in default namespace:',
                   'hca'
                   '/strat list hca',
                   '']
            strat_namespaces = self.namespaces
            strat_names      = self.strategies
            msg = msg + strat_namespaces + strat_names
            msg = '\n'.join(msg)
            
        else:
            namespace = args[1]
            strat_names = self.strategies
            msg = ['namespace:' + namespace]
            msg = msg + strat_names
            msg = '\n'.join(msg)

        bot.send_message(chat_id=update.effective_chat.id, text=msg)
        
    #def set_val(nm,val):
        #switcher={
                #'sig':'binary',
                   #'capital : self.capital,
                    #2:'Tuesday',
                    #3:'Wednesday',
                    #4:'Thursday',
                    #5:'Friday',
                    #6:'Saturday'
            #}
            #return switcher.get(i,"Invalid day of week")
            
    def _strat_select(self, bot, update, args):
        if (len(args) <2) or  (len(args) >3) :
            msg = ['message should have a format:',
                   '/strat select NAME (Use /strat list to find neames of supported strategies.)',
                   '/strat select <name:value>',
                   'for example:',
                   '/strat select MeanRevZ arkk',
                   '/strat select capital:10000  (capital base amount in USD)' ,
                   '/strat select sig:binary  (Signal Format:buy=1, hold=0,sell=-1)',
                   '/strat select sig:shares (Signal Format: num_shares )',
                   
                   ]
            msg = '\n'.join(msg)
        else:
            if len(args) == 2:
                cmd1 = args[1]
                nm, val = cmd1.split(':', 1)
                if nm=='capital':
                    self.capital = float(val)
                elif nm=='sig':
                    if val=='binary':
                        self.is_binary = True
                    elif val=='shares':
                        self.is_binary = False
                elif nm=='equity':
                    self.equity = val.upper()
                    
                msg = 'Set: name:value = {}:{}'.format(nm, val)
                
            elif len(args) == 3:
                nm = args[1]
                val = args[2]               
                self.strat_name = nm
                self.equity    = val.upper()
                namespace = self.strat_name.split('/')[0]
                msg = 'Selected strat: {} and Equity:{}'.format(self.strat_name, self.equity)
            
            
        bot.send_message(chat_id=update.effective_chat.id, text=msg)

    def _strat_help(self, bot, update):
        msg = """Available options are:\n
        /strat list NAMESPACE(=<hca|all|None>
        /strat select NAMESPACE/STRAT_NAME EQUITY
        """
        bot.send_message(chat_id=update.effective_chat.id, text=msg)
    # /stats latest <num_days> <tail> <asset_name>
    def _stats_latest(self, bot, update, args):
        if len(args) <= 4:
            sim_days = 2 * 365 # Default simulation days = 2 years = 2*365 days
            tail_days = 0
            if args[0]=='latest':
                if len(args) == 2:
                    sim_days = int(args[1])
                if len(args) == 3:
                    sim_days = int(args[1])                    
                    tail_days = int(args[2])                 
                if len(args) == 4:
                    sim_days = int(args[1])                    
                    tail_days = int(args[2])
                    asset_name = str(args[3])
                    self.equity = asset_name.upper()
                              
                end_dt  = pd.datetime.today()
                strt_dt = end_dt - pd.DateOffset(days=sim_days)                    
                strt_ts =  strt_dt.strftime("%Y-%m-%d")
                end_ts  = end_dt.strftime("%Y-%m-%d")
                print("start={} end={} simdays={} tail_days={} len(args)={}  args={}".format(strt_ts, end_ts, sim_days, tail_days, len(args), args))
                                        
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
                if tail_days >0:
                    stats_disp_td = bt_df[['Close','money','amount','equity']]
                    stats_disp_td         = stats_disp_td.tail(tail_days).sort_index(axis=0, ascending=False)
                    msg2               = stats_disp_td.to_string(index_names=True,justify='right')
                    msg2               = '```\n' + msg2 +  '```\n' #markdown pre-formatted
                    
                    
                msg = '\n'.join(msg)
                stats_msg_str = '\n'.join(stats_msg_list)
                #stats_render_md = self.strat.stats_calc(bt_df)
                #msg = msg + "\n" + stats_render_md + "\n" + perf_equity_md
                #msg = msg + "\n" + stats_render_md + "\n" + stats_msg_str
                msg1 = '```\n' + msg + "\n" + stats_msg_str + '```\n' 
                msg2 = '```\n' + f"\n\nLast {tail_days} of strategy\n\n" +  '```\n'

                #bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='html')
                bot.send_message(chat_id=update.effective_chat.id, text=msg1, parse_mode='MarkdownV2')
                if tail_days >0:
                    bot.send_message(chat_id=update.effective_chat.id, text=msg2, parse_mode='MarkdownV2')
                
        else:
            bot.send_message(chat_id=update.effective_chat.id, text="Command /stats {} is invalid.".format(args))
        
    def _stats_bt(self, bot, update, args):
        if len(args) != 5:
            msg = ['message should have format:',
                   '/stats bt EQUITY WINDOW START END',
                   'for example:',
                   '/stats bt SPY 11 2020-01-01 2021-03-23']
            msg = '\n'.join(msg)
            
        else:
            equity  = args[1].upper()
            self.equity =  equity
            window  = int(args[2])
            strt_ts = args[3]
            end_ts  = args[4]
            
            if not self.strat:
                self.strat = mr.MeanRevOneSymZ(strt_ts, end_ts)
                
            self.strat.asset_sym  = self.equity
            self.strat.capital = self.capital
            self.strat.window_len = window
             
            
            msg     = [f'Using equity {self.strat.asset_sym}',
                       f'with strategy: {self.strat_name}',
                       f'and window size: {self.strat.window_len}',
                       f'during period [{strt_ts} , {end_ts} ]',
                       '\n'
                       ]
            
                      
            stock       = self.strat.get_asset_data(self.strat.av_key, self.strat.asset_sym, strt_ts, end_ts)
            if stock is None:
                msg = f'Bad asset name: {self.strat.asset_sym}'
            else:
                bt_df       = self.strat.mr_trade(stock, self.strat.window_len)
                perf        = bt_df['equity'].calc_stats()
                                
                with ListStream() as stats_msg: # contextmanager to re-direct print-sysout to StringIO instance.
                    perf.display()
                              
                stats_msg_list = stats_msg.data.getvalue().splitlines()
                msg = '\n'.join(msg)
                stats_msg_str = '\n'.join(stats_msg_list)
                msg = msg + "\n" + stats_msg_str

        bot.send_message(chat_id=update.effective_chat.id, text=msg)

    def _stats_help(self, bot, update):
        msg = """Available options are:\n
        /stats latest SIM_DAYS TAIL_DAYS_DISP EQUITY_NAME
        /stats latest SIM_DAYS   (defaults: sim length=last 2years=last 730days, equity=SPY, window size=11)
        /stats bt EQUITY WINDOW START END  (run backtest, using EQUITY and WINDOW, from START to END dates)
        examples:
        /stats latest 3650
        /stats bt TSLA 7 2019-01-01 2021-03-23
        """
        bot.send_message(chat_id=update.effective_chat.id, text=msg)

    def _cmd_sig(self, bot, update, args):
        if (len(args) > 3) or (len(args)<2):
            msg = ['message should have a format:',
                   '/cmd sig DAYS (default=1)',  
                   'for example:',
                   '/cmd sig',
                   '/cmd sig 22  (last 22 days of this trading signal)',
                   '/cmd sig 22  arkk (last 22 days of the arkk  trading signal)']
            msg = '\n'.join(msg)
            bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='html')
            
        else:
            if len(args)==1:
                sig_days = 1
            elif len(args)==2:
                sig_days = int(args[1])
            else:
                sig_days = int(args[1])
                equity = args[2]
                equity = equity.upper()
                self.equity = equity
            

            sim_days= 2 * 365
            
            end_dt  = pd.datetime.today()
            strt_dt = end_dt - pd.DateOffset(days=sim_days)                    
            strt_ts =  strt_dt.strftime("%Y-%m-%d")
            end_ts  = end_dt.strftime("%Y-%m-%d")
            print("sig: start={} end={} simdays={} len(args)={}  args={}".format(strt_ts, end_ts, sim_days, len(args), args))
                                    
            msg1    = ['Using equity ',
                       self.equity,
                       'with strategy:',
                       self.strat_name,
                       'during period:',
                       '['+ strt_ts + ', ' + end_ts +']',
                       'producing CUR/TARG/SIG (+=BUY -=SELL)',
                       'for last {sig_days}',
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
            stats_disp         = stats_disp.tail(sig_days).sort_index(axis=0, ascending=False)
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

    def _cmd_plot(self, bot, update, args):
        if len(args) < 2:
            msg = ['Plot strategy column(s):',
                   '/cmd plot COL1 COL2' ,
                   'for example:',
                   '/cmd plot (Default value of COL1=equity)',
                   '/cmd plot equity',
                    '/cmd plot Close equity',
                    '/cmd plot comp  (Plot equity CumReturn: Close vs. Algo']
            msg = '\n'.join(msg)
            bot.send_message(chat_id=update.effective_chat.id, text=msg)
        else:
            sim_days = 2 * 365
            if len(args) == 2:
                series = [args[1]]
            elif len(args)==3:
                series = [args[1], args[2]]
            else:
               bot.send_message(chat_id=update.effective_chat.id, text=f"Bad command: /plot {args}") 

            end_dt  = pd.datetime.today()
            strt_dt = end_dt - pd.DateOffset(days=sim_days)                    
            strt_ts =  strt_dt.strftime("%Y-%m-%d")
            end_ts  = end_dt.strftime("%Y-%m-%d")
            print("plot: start={} end={} simdays={} len(args)={}  args={}".format(strt_ts, end_ts, sim_days, len(args), args))
                                    
            msg     = ['Using equity ',
                       self.equity,
                       'with strategy:',
                       self.strat_name,
                       'during period:',
                       '['+ strt_ts + ', ' + end_ts +']'
                       ]

            self.strat = mr.MeanRevOneSymZ(strt_ts, end_ts)
            self.strat.asset_sym = self.equity
            self.strat.money = self.capital
            
            stock      = self.strat.get_asset_data(self.strat.av_key, self.strat.asset_sym, strt_ts, end_ts)

            bt_df       = self.strat.mr_trade(stock, self.strat.window_len)
            
            fig = plt.figure()
            for channel_name in series:
                if channel_name != 'comp':
                    plt.plot(channel_name, data=bt_df,
                             marker='', linewidth=2, label=channel_name)
                elif channel_name == 'comp':
                    #bt_df = bt_df.rename(columns={'equity': self.strat.asset_sym})
                    bt_df['MeanRev-'+self.strat.asset_sym] = (bt_df[['equity']].pct_change()+1.).cumprod()
                    bt_df['Close-'+self.strat.asset_sym] = (bt_df[['Close']].pct_change()+1.).cumprod()
                    
                    for channel_name in ['MeanRev-'+self.strat.asset_sym, 'Close-'+self.strat.asset_sym]:
                        plt.plot(channel_name, data=bt_df,
                             marker='', linewidth=2, label=channel_name)
                else:
                    bot.send_message(chat_id=update.effective_chat.id, text=f"Bad command: /cmd plot  {series}") 
                    return
                    
            plt.legend()

            buffer = BytesIO()
            fig.savefig(buffer, format='png')
            buffer.seek(0)
            update.message.reply_photo(buffer)

    def _cmd_help(self, bot, update):
        msg = """Available options are:\n
        /cmd plot <options>
        /cmd sig <options>
        
        /cmd plot COL1 COL2 ,
                   for example:,
                   /cmd plot (Default value of COL1=equity)',
                   /cmd plot equity,
                   /cmd plot Close equity
                   
        /cmd sig <options>
        /cmd sig <num_tail_days>
        /cmd sig <num_tail_days> <equity>
        """
        bot.send_message(chat_id=update.effective_chat.id, text=msg)

    def _no_strat_selected(self, bot, update):
        msg = ["You haven't selected your strategy.",
               "Do so by running:\n"
               "/strategy select STRATEGY",
               "For example:",
               "/strategy select mr"]
        msg = '\n'.join(msg)
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
        
