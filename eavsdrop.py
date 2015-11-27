import glib
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from subprocess import PIPE, Popen
import time
import logging
import multiprocessing

# global variables
last_switch_inside_task_group = []
last_switch_outside_task_group = []


def window_tracker():
    title = ''
    pid = 0
    root_check = ''
    members = []
    entry = []
    members = []
    entry = []
    last_entry = -1

    while True:
        time.sleep(0.6)
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
                        members, entry, last_entry = get_windows_groupings(title, int(time.time()), members, entry,  last_entry)
                        timepoints = calculatepoints(members, last_entry)
                        update_last_switch_events(timepoints, title)


def update_last_switch_events(timepoints, new_window):
    global last_switch_inside_task_group
    global last_switch_outside_task_group
    sum_points = 0.0
    sum_timepoints = 0.0
    group = []
    for p in timepoints:
        sum_points += timepoints[p][1]
        sum_timepoints += timepoints[p][0]
    #logger.debug("Sum of window points are: %d %d" % sum_points % sum_timepoints)
    for window in timepoints:
        value = (timepoints[window][1] / sum_points) + (timepoints[window][0] / sum_timepoints)
        #logger.debug("Total value of " + window + " is: " + value)
        if value > 0.30:
            group.append(window)
    if new_window in group:
        #logger.info("The new window: " + new_window + " belongs to the current task group")
        last_switch_inside_task_group = [new_window, int(time.time())]
        last_switch_outside_task_group = []
    else:
        #logger.info("The new window: " + new_window + " DOESN'T belong to the task group")
        last_switch_outside_task_group = [new_window, int(time.time())]
        last_switch_inside_task_group = []


def get_windows_groupings(window_name, timestamp, members, entry, lastentry):
    window = 600
    # set higher and lower bounds of the window
    higherbound = timestamp
    lowerbound = higherbound - window
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
            logger.debug("Window: " + entry[0] + " too old, removing from current windows")
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
        logger.debug("Timepoints contains: %d" % timepoints[item[0]][0])
        timepoints[item[0]][1] += 1
        #logger.debug("Window: '{0}' gained '{1}' timepoints and '{2}' points".format(item[0],
        #            timepoints[item[0]][0],timepoints[item[0]][1]))
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


def run_struf():glib.MainLoop().run()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
loop = DBusGMainLoop(set_as_default=True)
session_bus = dbus.SessionBus()
session_bus.add_match_string(
    "type='method_call',interface='org.freedesktop.Notifications',member='Notify',eavesdrop=true")
session_bus.add_message_filter(print_notification)

p = multiprocessing.Process(target=run_struf())
p.start()
thread = multiprocessing.Process(target=window_tracker())
thread.start()

print "test"
