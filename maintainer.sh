#!/bin/bash

if [[ -n "$1" ]]; then
	DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
	
	while true
	do
		if pgrep -f "EloBot/main\.py" 1>/dev/null;then
			sleep 5
		else
			echo "Bot not found, restarting it with data: $1"
			echo "Calling: $DIR/run.sh $1"
			$DIR/run.sh $DIR/$1
		fi
	done
else
	echo "Argument error - pass data_folder path to the script"
fi