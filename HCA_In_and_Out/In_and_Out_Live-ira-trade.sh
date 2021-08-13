#!/bin/bash
#set -v

. ~/hca/hca.env

DT=`date +%F`
echo "Date=${DT}"

echo "zipline run -s ${DT} -f /home/hca-ws2004/hca/hca-resources/HCA_In_and_Out/HCA_In_and_Out_Live-IRA.py --bundle sharadar-funds --broker ib --broker-uri 127.0.0.1:7499:1301 --broker-acct U4169274 --data-frequency daily --state-file /home/hca-ws2004/hca/hca-resources/HCA_In_and_Out/strategy-U4169274.state --realtime-bar-target /home/hca-ws2004/hca/hca-resources/HCA_In_and_Out/realtime-bars/"

zipline run -s ${DT} -f /home/hca-ws2004/hca/hca-resources/HCA_In_and_Out/HCA_In_and_Out_Live-IRA.py --bundle sharadar-funds --broker ib --broker-uri 127.0.0.1:7499:1301 --broker-acct U4169274 --data-frequency daily --state-file /home/hca-ws2004/hca/hca-resources/HCA_In_and_Out/strategy-U4169274.state --realtime-bar-target /home/hca-ws2004/hca/hca-resources/HCA_In_and_Out/realtime-bars/
