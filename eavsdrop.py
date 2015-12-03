import glib
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from subprocess import PIPE, Popen
import time
import logging
import multiprocessing
import os

# global variables
last_switch_inside_task_group = []
last_switch_outside_task_group = []
user_has_been_inactive = False
user_idle_threshold = 300000 # 5 minutes in milliseconds
noise_collection_time = '3' #seconds
noise_threshold = 500 # have no idea what this is
noise_threshold_passed = False
window_grouping_time_range = 300

#TODO: fix timepoints problems


def is_voice_playing():
    count = 0
    sound_file = Popen('cat /proc/asound/card*/pcm*/sub*/status', shell=True, stdout=PIPE)
    for line in sound_file.stdout:
        line = line.split(":")
        if line[0] == "state":
            count += 1
            #logger.debug("line is :%s" % line[1].rstrip().replace(" ",""))
            if count == 2:
                if line[1].rstrip().replace(" ","") == "RUNNING": #beware there is a space here
                    #logger.debug("A sound card is running because %s detected" % line)
                    return True
    return False

def window_tracker():
    title = ''
    pid = 0
    root_check = ''
    members = []
    entry = []
    last_entry = -1
    global user_has_been_inactive
    while True:
        time.sleep(0.6)
        inactivity = Popen(['xprintidle'], stdout=PIPE)
        for timer in inactivity.stdout:
            if int(timer) > user_idle_threshold:
                if not is_voice_playing():
                    user_has_been_inactive = True
                    #logger.debug("User inactivity logged at %d" % int(time.time()))
                else:
                    user_has_been_inactive = False
            else:
                user_has_been_inactive = False

        root = Popen(['xprop', '-root'], stdout=PIPE)

        if root.stdout != root_check:
            root_check = root.stdout
            for i in root.stdout:
                if '_NET_ACTIVE_WINDOW(WINDOW):' in i:
                    id_ = i.split()[4]
                    id_w = Popen(['xprop', '-id', id_], stdout=PIPE)

            for j in id_w.stdout:
                if '_NET_WM_PID' in j:
                    if pid != j.split()[2]:
                        pid = j.split()[2]
                        pid = pid.rstrip()
                        logger.info("Current window PID: %s" % pid)
                        title_pipe = Popen(['ps', '-p', pid, '-o', 'comm='], stdout=PIPE)
                        for z in title_pipe.stdout:
                            title = z
                            title = title.rstrip()
                        logger.info("Current window title: %s" % title)
                        members, entry, last_entry = get_windows_groupings(title, int(time.time()), members, entry,
                                                                           last_entry)
                        timepoints = calculatepoints(members, last_entry)
                        update_last_switch_events(timepoints, title)


def update_last_switch_events(timepoints, new_window):
    global last_switch_inside_task_group
    global last_switch_outside_task_group
    sum_points = 0.0
    sum_timepoints = 0.0
    d = 1.2
    group = []
    for p in timepoints:
        sum_points += int(timepoints[p][1])
        sum_timepoints += int(timepoints[p][0])
    logger.debug('Sum of window points are: %6.2f and  %6.2f', sum_points, sum_timepoints )
    for window in timepoints:
        switch_value = timepoints[window][1] * 100 / sum_points
        time_value =  timepoints[window][0] * 100 / sum_timepoints
        value = time_value + switch_value
        logger.debug("Time value of '%s' is: %d and switch value is: %d", window, time_value, switch_value)
        # each value should at least be bigger than 10% : case => {'chrome': [5, 1], 'gnome-terminal': [7660, 1]}
        # in the above case switch_value gets 50 but time gets 0. gnome-terminal should not belong to the group
        if value > 30 and time_value >= 10 and switch_value >= 10:
            group.append(window)
    if new_window in group:
        logger.info("The new window: %s belongs to the current task group" %new_window)
        last_switch_inside_task_group = [new_window, int(time.time())]
        last_switch_outside_task_group = []
    else:
        logger.info("The new window: %s  DOESN'T belong to the task group" %  new_window )
        last_switch_outside_task_group = [new_window, int(time.time())]
        last_switch_inside_task_group = []


def get_windows_groupings(window_name, timestamp, members, entry, lastentry):
    global window_grouping_time_range
    # set higher and lower bounds of the window
    higherbound = timestamp
    lowerbound = higherbound - window_grouping_time_range
    line = [window_name, timestamp]
    # be prepared for the first entry
    if lastentry == -1:
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
            logger.debug("Window: %s too old, removing from current windows" % entry[0])
    return members, entry, lastentry


def calculatepoints(members, lastentry):
    """
    __name__ = "calculate_points"
    :rtype : Dictionary
    """
    points = {}
    timepoints = {}
    # timepoints => {window name -> [timepoints,points] }
    i = 0
    # assign one point for each second that a window was in focus
    while i < len(members):
        if i == 0:
            temp = int(members[i][1]) - lastentry
            timepoints[members[i][0]] = [temp, 0]
        else:
            if members[i][0] in timepoints:
                timepoints[members[i][0]][0] += int(members[i][1]) - int(members[i - 1][1])
            else:
                timepoints[members[i][0]] = [int(members[i][1]) - int(members[i - 1][1]), 0]
        i += 1
    # assign one point for each occurence of the window in focus
    for item in members:
        #logger.debug("Timepoints of item: %s contains: %d", item[0], timepoints[item[0]][0])
        timepoints[item[0]][1] += 1
        #logger.debug("Window: '{0}' gained '{1}' timepoints and '{2}' points".format(item[0],
        #            timepoints[item[0]][0],timepoints[item[0]][1]))
    logger.debug(timepoints)
    return timepoints


def print_notification(bus, message):
    keys = ["app_name", "replaces_id", "app_icon", "summary",
            "body", "actions", "hints", "expire_timeout"]
    args = message.get_args_list()
    if len(args) == 8:
        notification = dict([(keys[i], args[i]) for i in range(8)])
        logger.info(
            "New notification arrived with details: " + notification["summary"] + notification["body"] + notification[
                'app_name'])


def get_noise_level():
    redirect_devnull = open(os.devnull,'w')
    global noise_threshold_passed, noise_threshold, noise_collection_time
    while True:
        total_noise = Popen(['soundmeter', '--collect', '--seconds', noise_collection_time],
                            stdout=PIPE, stderr=redirect_devnull)
        for noise in total_noise.stdout:
            if "avg" in noise:
                noise = int(noise.split(":")[1].rstrip())
                logger.debug("Noise levels are %d at %d", noise, time.time())
                if noise > noise_threshold:
                    noise_threshold_passed = True
                else:
                    noise_threshold_passed = False

        time.sleep(5)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
loop = DBusGMainLoop(set_as_default=True)
session_bus = dbus.SessionBus()
session_bus.add_match_string(
    "type='method_call',interface='org.freedesktop.Notifications',member='Notify',eavesdrop=true")
session_bus.add_message_filter(print_notification)

notification_collector = multiprocessing.Process(target=glib.MainLoop().run)
notification_collector.start()
activity_tracker = multiprocessing.Process(target=window_tracker)
activity_tracker.start()
noise_tracker = multiprocessing.Process(target=get_noise_level)
#noise_tracker.start()