#!/usr/bin/env python
# coding: utf-8

#pip install python-telegram-bot
import telegram
import time
import schedule
from time import gmtime, strftime
from pathlib import Path

#HCA-Telegram-Bots.csv
#    chili_mr_bot	 @HCA-MeanRev	t.me/chili_mr_bot	 1778031894:AAFWbqVjM_AThOMlU6BZDzlQN44go9AFg4E
TOKEN = '1778031894:AAFWbqVjM_AThOMlU6BZDzlQN44go9AFg4E'

#CHAT_IDS = ['@afjgta']
#CHAT_IDS = ['@AFJGTestChat']
###afjg original CHAT_IDS = ['@AFJGTestChannel','@AFJGTestChat']
CHAT_IDS = ['@hotchilianalytics', '@hotchilianalyticschat']
bot = telegram.Bot(token=TOKEN)
print(bot.get_me())

import os
hca_root_path = os.environ['HCA_ROOT']
print(f"hca_root_path = {hca_root_path}")

import subprocess
import sys, os, inspect
from distutils.util import strtobool
import logbook
import pathlib as pl
import pandas as pd

from pathlib import Path
import pprint as pp


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

def get_script_dir(follow_symlinks=True):
    if getattr(sys, 'frozen', False): # py2exe, PyInstaller, cx_Freeze
        path = os.path.abspath(sys.executable)
    else:
        path = inspect.getabsfile(get_script_dir)
    if follow_symlinks:
        path = os.path.realpath(path)
    return os.path.dirname(path)

path = get_script_dir()
#LOCAL_BOT_LIVE_PATH=Path(path).parent / "telegram"
LOCAL_BOT_LIVE_PATH = Path(path)
#LOCAL_BOT_LIVE_PATH = Path(path) / (Path(path).stem + "_Bot")
sys.path.append(os.path.abspath(LOCAL_BOT_LIVE_PATH))

pp.pprint(f'path={path} bot_path={LOCAL_BOT_LIVE_PATH}')

# In[5]:
#/start - List of Commands (This one)
#/help  - Some help on using our Bot
#/about - Who we are and what we do

#/cmd   - Algo currently running
#/so    - Orders for the day for the SaasSec Algo
#/sbt   - Latest backtest chart for the SaasSec Algo
#/stats - Recorded tearsheet performance variables
#/verif - Rebalance trade verification. Share: Old-New-Chg

#/trade - Put on todays trades for the SaasSec Algo
#/exit  - Exit all positions in your brokerage account


TELEGRAM_PATH = LOCAL_BOT_LIVE_PATH
#TELEGRAM_PATH = hca_root_path + "/hca-telegram/"
CHARTS = TELEGRAM_PATH / 'charts.png'

ALGOSTATS_PATH = LOCAL_BOT_LIVE_PATH
ALGOSUMM_PATH = LOCAL_BOT_LIVE_PATH


START = TELEGRAM_PATH / 'start_command.csv'
HELP  = TELEGRAM_PATH / 'help_command.txt'
ABOUT = TELEGRAM_PATH / 'about_command.txt'

# Algo Bespoke Command Locations
CMD   = ALGOSTATS_PATH / 'cli_args_run_file-Live.sh'
SO    = ALGOSTATS_PATH / 'all_orders.csv'
SPP    = ALGOSTATS_PATH / 'portfolio_pct_total.csv'

SBT   = CHARTS 
STATS = ALGOSUMM_PATH / 'port_summ_file.txt'
VERIF = ALGOSTATS_PATH / 'order_verif.csv'


TEXTSTART = TELEGRAM_PATH /  'start_command.txt'

TRADE = TELEGRAM_PATH / 'trade_command.txt'
EXIT = TELEGRAM_PATH / 'exit_command.txt'

LOG = TELEGRAM_PATH / 'log.log'

print(f"""
TELEGRAM_PATH        = {TELEGRAM_PATH}
LOG                  = {LOG}
START                = {START}
TEXTSTART            = {TEXTSTART}
HELP                 = {HELP}
EXIT                 = {EXIT}
ABOUT                = {ABOUT}
TRADE                = {TRADE}
CMD                  = {CMD}
SO                   = {SO}
SPP                  = {SPP}
SBT                  = {SBT}
STATS                = {STATS}
VERIF                = {VERIF}


Contents of telegram directory:
""")
#get_ipython().system('ls $TELEGRAM_PATH')
#subprocess.run(["ls",$TELEGRAM_PATH], check=True)

#import logging
#logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#                     level=logging.INFO)
import logging

# return a logger with the specified name & creating it if necessary
logger = logging.getLogger(__name__)

# create a logger handler, in this case: file handler
file_handler = logging.FileHandler(LOG)
# set the level of logging to INFO
file_handler.setLevel(logging.INFO)

# create a logger formatter
logging_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# add the format to the logger handler
file_handler.setFormatter(logging_format)

# add the handler to the logger
logger.addHandler(file_handler)

photo_caption_1 = "Latest Charts for Segmec System"

def get_asset_data(av_key, asset_sym, strt_date, end_date):
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
def mr_trade(stock, length):
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

# ### Code for Broadcasting to the Channel
#functions
def post_message(message):
    """
    Posts a message to the telegram bot chats / or channel
    :param str message: A string message
    :return: None
    """
    try:
        for id in CHAT_IDS:
            bot.send_message(id, message)
    except:
        print('error handling code to be drafted')
    return

def post_photo(photo,caption):
    """
    Posts a photo to the telegram bot chats / or channel
    :param str message: A string message
    :return: None
    """
    try:
        for id in CHAT_IDS:
            bot.send_photo(id, photo = open(photo,'rb'),caption= caption)
    except:
        print('error handling code to be drafted')
    return

def post_file_content(file):
    """
    Open file and convert content to string
    :param csv fie
    :return: None
    """
    try:
        with open(file) as f:
            s = f.read() #+ '\n' # add trailing new line character
            f.close()
        for id in CHAT_IDS:
            bot.send_message(id, s)
    except:
        print('error handling code to be drafted')
    return

def read_text(file):
    """
    Open file and convert content to string, return string
    :param csv file
    :return: String
    """
    try:
        with open(file) as f:
            s = f.read() 
    except:
        s = 'No file to read: {}'.format(file)
    return s

#telegram.Bot(token=TOKEN).send_photo('@afjgta', photo = open(photo,'rb'),caption= caption)

# ####  The following function contains the jobs to be scheduled

def job():
    post_file_content(RESULTS_CSV)
    post_photo(CHARTS,photo_caption_1)    
    return

# #### And here is the scheduler which is just left running

# Scheduling
#schedule.every(20).seconds.do(job)

#schedule.every(30).seconds.do(post_message, message = SMA)
#schedule.every(40).seconds.do(post_message, message = LMA)
#schedule.every().hour.do(job)
#schedule.every().day.at("10:30").do(job)
#schedule.every(5).to(10).minutes.do(job)
#schedule.every().monday.do(job)
###schedule.every().sunday.at("18:55").do(job)
#schedule.every().minute.at(":17").do(job)

#while True:
   #schedule.run_pending()
   #time.sleep(1)


# ### Code for the Bot's Responses to Commands

from telegram.ext import CommandHandler
from telegram.ext import Updater
updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher


def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=read_text(TEXTSTART))

start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)


def help(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=read_text(HELP))

help_handler = CommandHandler('help', help)
dispatcher.add_handler(help_handler)

def about(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=read_text(ABOUT))

about_handler = CommandHandler('about', about)
dispatcher.add_handler(about_handler)


def cmd(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=read_text(CMD))

cmd_handler = CommandHandler('cmd', cmd)
dispatcher.add_handler(cmd_handler)

def so(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=read_text(SO))

so_handler = CommandHandler('so', so)
dispatcher.add_handler(so_handler)

def spp(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=read_text(SPP))

spp_handler = CommandHandler('spp', spp)
dispatcher.add_handler(spp_handler)

def sbt(update, context):
    context.bot.send_photo(chat_id=update.effective_chat.id,photo = open(CHARTS,'rb'),caption= photo_caption_1)

sbt_handler = CommandHandler('sbt', sbt)
dispatcher.add_handler(sbt_handler)

def spp(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=read_text(SPP))

spp_handler = CommandHandler('spp', spp)
dispatcher.add_handler(spp_handler)

def verif(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=read_text(VERIF))

verif_handler = CommandHandler('verif', verif)
dispatcher.add_handler(verif_handler)


def trade(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=read_text(TRADE))

trade_handler = CommandHandler('trade', trade)
dispatcher.add_handler(trade_handler)

def exit(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=read_text(EXIT))

exit_handler = CommandHandler('exit', exit)
dispatcher.add_handler(exit_handler)

ASSET_SYM = 'SPY'
AV_KEY    = 'HK7Q1K6I2EIFKTVL'
strt_date = "2019-01-01"
end_date  = "2021-03-19"
moving_average = 11 #15 #10

def stats(update, context):
    stock = get_asset_data(AV_KEY, ASSET_SYM, strt_date, end_date)
    profit = mr_trade(stock, moving_average)
    profit.to_csv('mean_reversion_profit.csv')
    #    
    # Write output exhaust to  Bot dir
    #profit = pd.read_csv(str(LOCAL_BOT_LIVE_PATH) + '/mr.csv')
    # SPY series. May need to be shifted down by one, like profit
    #data = pd.read_csv(str(LOCAL_BOT_LIVE_PATH) + '/spy.csv')
    
    #profit_html = profit[['Date','Close','position_count','equity']].tail().to_html(classes=None, border='0', justify=None)
    #profit_md = profit[['Date','Close','position_count','equity']].tail(10).to_markdown()
    #profit_md = profit[['Close','position_count','equity']].tail(10).to_markdown(index=False)
    #profit_md = profit[['Close','position_count','equity']].tail(10).to_string(index=True)
    profit = profit.reset_index()
    #profit_md = profit[['Date','Close','position_count','equity']].tail(10)
    profit_md = profit[['Date','Close','amount','equity']].tail(22)
    #profit_md['Date'] = [d.strftime('%Y-%m-%d') if not pd.isnull(d) else '' for d in profit_md['Date']]
    profit_md['Date'] = [d.strftime('%y-%m-%d') if not pd.isnull(d) else '' for d in profit_md['Date']]
    
    ###profit_md_render1 = profit_md.to_string(index=False)
    ###profit_md_render2 = profit_md.to_markdown(index=False)
    profit_md_render3 = profit_md.to_markdown(index=False)
    ###profit_md_render4 = profit_md.to_html(index=False)
    # Send a message with the stats
    #context.bot.send_message(chat_id=update.effective_chat.id, text=read_text(STATS))
    #context.bot.send_message(chat_id=update.effective_chat.id, text=profit_md, parse_mode='MarkdownV2')
    #context.bot.send_message(chat_id=update.effective_chat.id, text=profit_md, parse_mode='html')
    ###context.bot.send_message(chat_id=update.effective_chat.id, text=profit_md_render1)
    #context.bot.send_message(chat_id=update.effective_chat.id, text=profit_md_render2, parse_mode='MarkdownV2')
    context.bot.send_message(chat_id=update.effective_chat.id, text=profit_md_render3, parse_mode='html')
    #context.bot.send_message(chat_id=update.effective_chat.id, text=profit_md_render4, parse_mode='html')
    #msg = (
        #"HCA Strat: "
        #+ " stats: "
        #+ str(10.0)
    #)
#    update.message.reply_text(msg)

# on different commands - answer in Telegram
stats_handler = CommandHandler('stats', stats)
dispatcher.add_handler(stats_handler)

from telegram.ext import MessageHandler, Filters
def unknown(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I didn't understand that command.")

unknown_handler = MessageHandler(Filters.command, unknown)
dispatcher.add_handler(unknown_handler)

updater.start_polling()
# Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
updater.idle()


