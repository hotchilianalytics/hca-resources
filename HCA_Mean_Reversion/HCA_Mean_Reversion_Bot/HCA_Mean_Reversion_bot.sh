#!/bin/bash

echo
echo
echo "Telegram bot:@HCA-MeanRev with  @chili_mr_botwill open automatically, please be patient."
echo
echo

. ~/hca/hca.env
python ~/hca/hca-resources/HCA_Mean_Reversion/HCA_Mean_Reversion_Bot/hca_bot.py -t '1778031894:AAFjDfqUmSb8yurVwT9ZNqUumKv2YEEPWD4'
read -rsp $'\n\nPress any key to close this window.\n\n' -n1 key

