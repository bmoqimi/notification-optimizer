#!/bin/bash

# A daemon that tracks the applications in focus and records them for futhur analysis.

# 1) get the current in focus PID
# 2) Find the application name
# 3) record it in a file with timestamp
mkdir -p ~/.trackerinfo
TRACKER="$HOME/.trackerinfo/tracker.log"
oldAPP="nothing"
while [ true ]
do
	currentAPP=`xprop -id $(xprop -root 32x '\t$0' _NET_ACTIVE_WINDOW | cut -f 2) _NET_WM_NAME | cut -d= -f2`
	currentPID=`xprop -id $(xprop -root 32x '\t$0' _NET_ACTIVE_WINDOW | cut -f 2) _NET_WM_PID | cut -d= -f2`
	currentName=`ps -p $currentPID -o comm=`
	if [ "$currentAPP" != "$oldAPP" ]
	then
		oldAPP=$currentAPP
		time=`date +%s`
		printf "$currentAPP\t$currentName\t$time\n" >> $TRACKER
	fi
	sleep 2
done
