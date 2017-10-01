#!/bin/bash

# Add this script to autorun (from your user for example)
# su pi -c "/path/to/script/run_maintainer.sh"
# Dont forget to chomd +x *.sh there!

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
screen -dmS BotMaintainer $DIR/maintainer.sh "Data"
echo "Bot maintainer started, check screen -list to find it"