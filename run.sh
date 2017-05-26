#!/bin/bash

echo "Starting EloBot..."

if [[ -n "$1" ]]; then
	echo "Selected folder: $1"
	DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
	echo "Calling: screen -dmS EloBot /usr/bin/python3 $DIR/main.py $1"
	screen -dmS EloBot /usr/bin/python3 $DIR/main.py $1
	echo "EloBot started, check screen -list to find it"
else
	echo "Argument error - pass data_folder path to the script"
fi