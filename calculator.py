#!/usr/bin/env python
import sys

window = 600
# interval = 60
lastentry = -1
members = []


def get_windows_groupings(window_name,timestamp):

    # set higher and lower bounds of the window
    higherbound = timestamp
    lowerbound = higherbound - window
    line= [window_name,timestamp]
    # be prepared for the first entry
    if len(members) == 0:
        lastentry = int(line[1]) - 10
        members.append(line)
    elif members[len(members) - 1] != line[0]:
        members.append(line)
    else:
        members[len(members) - 1][1] = line[1]
    # remove the out of date entry in members
    for entry in members:
        if int(entry[1]) < lowerbound:
            lastentry = int(entry[1])
            members.remove(entry)
    # re-evaluate the points
    points, timepoints = calculatepoints(members, lastentry)

def calculatepoints(members, lastentry):
    points = {}
    timepoints = {}
    i = 0
    # assign one point for each second that a window was in focus
    while i < len(members):
        if i == 0:
            timepoints[members[i][0]] = int(members[i][1]) - lastentry
        else:
            if members[i][1] in timepoints:
                timepoints[members[i][1]] += int(members[i][1]) - int(members[i - 1][1])
            else:
                timepoints[members[i][1]] = int(members[i][1]) - int(members[i - 1][1])
        i += 1
    # assign one point for each occurence of the window in focus
    for item in members:
        if item[1] in points:
            points[item[0]] += 1
        else:
            points[item[0]] = 1
    return points, timepoints
