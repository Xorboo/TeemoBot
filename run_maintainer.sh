#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
screen -dmS BotMaintainer $DIR/maintainer.sh "Data" | tee -a ~/Documents/bot_maintainer.log
echo "Bot maintainer started, check screen -list to find it"