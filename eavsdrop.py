import glib
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from subprocess import PIPE, Popen
import time
import logging
import threading
import os
import pynotify
import sys
import glob
import traceback
import database


try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser  # ver. < 3.0


# global variables
all_applications_categories = {}
last_switch_inside_task_group = [] # [title_of_current_window, timestamp of arrival]
last_switch_outside_task_group = [] # same ^
user_has_been_inactive = False
user_idle_threshold = 300000 # 5 minutes in milliseconds
noise_collection_time = '3' #seconds
noise_threshold = 1200 # have no idea what this is
noise_threshold_passed = False
window_grouping_time_range = 300
cost_threshold = 0 #smaller than this are showed only
notification_queue = []
noise_check_interval = 120 #seconds
notification_showing_interval = 3 # seconds of sleeping before dumping the to-be-shown queue
queue_check_interval = 120 # seconds after which the queue is re-evaluated
notifications_to_be_shown = [] # ready notifications are stored here to be picked up later
focused_application_categories = ["development", "java", "utility"] # TODO: Complete this list
my_app_name = "TestApp"
discard_notification_action = "discard"
accept_notification_action = "accept"
open_notification_action = "open"
notifications_already_shown = []
feedback_list = []
trigger_lock = 1


def trigger_cost_analysis(invoker):
    global notification_queue, trigger_lock
    logger.debug("New cost analysis triggered by %s " %invoker)
    if trigger_lock == 0:
        return
    # this lock can break every one in a million times so who cares?
    trigger_lock = 0
    temp_queue = notification_queue
    notification_queue = []
    for item in temp_queue:
        logger.debug("Cost analysis trigger is going to process the queue now.")
        process_new_notification(item[0], item[1])
        time.sleep(notification_showing_interval)
    trigger_lock = 1


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
                    if not user_has_been_inactive:
                        user_has_been_inactive = True
                        logger.debug("User inactivity logged at %d" % int(time.time()))
                        trigger_cost_analysis("Inactivity Tracker")
                        #noti = {'summary':'stuff','app_name':my_app_name,'body':'testing'}
                        #notifications_to_be_shown.append(noti)
                        #test.append(time.time())
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
                                #logger.debug("Current window PID: %s" % pid)
                                title_pipe = Popen(['ps', '-p', pid, '-o', 'comm='], stdout=PIPE)
                                for z in title_pipe.stdout:
                                    title = z
                                    title = title.rstrip()
                                #logger.debug("Current window title: %s" % title)
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
    logger.debug('Sum of window points are: %6.2f and  %6.2f', sum_points, sum_timepoints)
    if sum_points == 0:
        sum_points += 1
    if sum_timepoints == 0:
        sum_timepoints += 1
    
    for window in timepoints:
        switch_value = timepoints[window][1] * 100 / sum_points
        time_value =  timepoints[window][0] * 100 / sum_timepoints
        value = time_value + switch_value
        #logger.debug("Time value of '%s' is: %d and switch value is: %d", window, time_value, switch_value)
        # each value should at least be bigger than 10% : case => {'chrome': [5, 1], 'gnome-terminal': [7660, 1]}
        # in the above case switch_value gets 50 but time gets 0. gnome-terminal should not belong to the group
        if value > 30 and time_value >= 10 and switch_value >= 10:
            group.append(window)
    if new_window in group:
        #logger.info("The new window: %s belongs to the current task group" %new_window)
        last_switch_inside_task_group = [new_window, int(time.time())]
        last_switch_outside_task_group = []
        trigger_cost_analysis("switch INSIDE task group")
    else:
        #logger.info("The new window: %s  DOESN'T belong to the task group" %  new_window )
        last_switch_outside_task_group = [new_window, int(time.time())]
        last_switch_inside_task_group = []
        trigger_cost_analysis("Switch OUTSIDE task group")


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
            #logger.debug("Window: %s too old, removing from current windows" % entry[0])
    #logger.debug("These are members: " + str(members))
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
    length = len(members)
    for item in members:
        timepoints[item[0]] = [0,0]
    if length == 1:
        temp = int(members[0][1]) - lastentry
        timepoints[members[0][0]] = [temp, 0]
    else:
        while i < length -1:
            timepoints[members[i][0]][0] += int(members[i + 1][1] - int(members[i][1]))
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
    #logger.debug("This is the bus: %s" % str(message))
    global last_switch_outside_task_group, last_switch_inside_task_group
    keys = ["app_name", "replaces_id", "app_icon", "summary",
            "body", "actions", "hints", "expire_timeout"]
    args = message.get_args_list()
    if len(args) == 8:
        notification = dict([(keys[i], args[i]) for i in range(8)])
        logger.info("New notification arrived with details: %s" % str(notification) )
        if notification['app_name'] == my_app_name:
            logger.debug("Notification was sent by ourselves ... ignoring it.")
            return
        try:
            if len(last_switch_inside_task_group) == 0:
                db.save_notification(notification, last_switch_outside_task_group[0])
            else:
                db.save_notification(notification, last_switch_inside_task_group[0])
        except Exception, e:
            logger.debug("Inserting notification to db failed with: %s" % e.args[0])
            traceback.print_exc()
            sys.exit(7)

        process_new_notification(notification, time.time())


def process_new_notification(notification, arrival_time):
    logger.debug("Processing new notification with summary: %s" %notification['summary'])
    global notifications_to_be_shown
    try:
        score = get_current_notification_score(notification, arrival_time)
        if score <= cost_threshold:
            notifications_to_be_shown.append(notification)
        else:
            queue_notification(notification, arrival_time)
    except TypeError as e:
        #e = sys.exc_info()[0]
        logger.debug("Processing new notification failed with %s" % str(e))

def get_current_notification_score(notification, arrival_time):
    cost = 0
    # Maximum 30 seconds after the user went in 'Focused Mode':
    if len(last_switch_inside_task_group) != 0:
        current_window = last_switch_inside_task_group[0]
        time_in_focus = int(time.time()) - last_switch_inside_task_group[1]
        if time_in_focus < 5:
            cost -= 50
        elif time_in_focus < 30:
            cost -= time_in_focus * 1
        elif time_in_focus < 300:
            cost += time_in_focus * 1 # for readability purposes only
        else:
            cost -= 300
    elif len(last_switch_outside_task_group) != 0:
        current_window = last_switch_outside_task_group[0]
        time_in_focus  = int(time.time()) - last_switch_outside_task_group[1]
        if time_in_focus < 5:
            cost -= 500
        elif time_in_focus < 30:
            cost -= time_in_focus * 6
        elif time_in_focus < 300:
            cost += time_in_focus * 0.5
        else:
            cost -= 300 # same reason here ^

    logger.debug("Cost of notification after item 1: %s" % str(cost))

    # Current Application Type
    if current_window in all_applications_categories:
        my_categories = all_applications_categories[current_window]
        has_shared_categories = any([ item in my_categories for item in focused_application_categories])
        logger.debug("has shared cats: %s " % str(has_shared_categories))
        if has_shared_categories:
            # This means the current application needs focus (e.g: development env)
            cost += 100
        else:
            cost -= 100
    # Each Second Since this window/Task is in focus --> already implemented above ^
    logger.debug("Cost of notification after category calculation: %s" % str(cost))

    # Obstruction Cost
    # Ambient Noise:
    if noise_threshold_passed:
        cost -= 50
    else:
        cost += 50
    logger.debug("Cost of notification after noise calculation: %s" % str(cost))

    # Background Running Application

    # Each second of waiting in Queue
    time_in_queue = int(time.time()) - arrival_time
    cost -= time_in_queue * 0.5

    logger.debug("Cost of notification after waiting time in queue calculation: %s" % str(cost))

    # Each Positive feedback from user for this type of notification
    if "app_name" in notification:
        sender = notification["app_name"]
        if sender != "":
            feedbacks = db.get_window_feedback(sender)
            if len(feedbacks) != 0:
                accept = feedbacks[0]
                reject = feedbacks[1]
                if accept <= 10:
                    cost -= accept * 20
                else:
                    cost -= 200
                if reject <= 10:
                    cost += reject * 20
                else:
                    cost += 200

    logger.debug("Cost of notification after feedback calculation: %d" % cost)

    # 11 File saved Event

    # 12 During Typing Event

    #13,14 Switch Application - to outside of the Current -500 Task group event
    # Implemented using triggers in item #1

    #15 user inactive event
    # again implemented using triggers
    if user_has_been_inactive:
        cost -= 800

    logger.debug("Final cost of notification calculated as: %d " % cost)
    return cost


def show_notification():
    time_counter = 0
    if not pynotify.init(my_app_name):
        sys.exit(1)
    while True:
        global notifications_to_be_shown, notifications_already_shown, notification_queue
        time_counter += 1
        if time_counter % 10 == 0:
            if len(notification_queue) != 0:
                trigger_cost_analysis("Notification Queue Manager")
        icon, body, title = '','',''
        #logger.debug("Checking for new notifications .... %s" % str(user_has_been_inactive))
        if len(notifications_to_be_shown) != 0:
            logger.debug("New notification found... will process it now")
            notification = notifications_to_be_shown[0]
            if "summary" in notification:
                title = notification['summary']
            if "body" in notification:
                body = notification['body']
            if 'app_icon' in notification:
                icon = notification['app_icon']
            #sender = my_app_name
            n = pynotify.Notification(title, body, icon)
            logger.debug("Going to show notification with summary: %s" %title)
            n.add_action(discard_notification_action, discard_notification_action, reject_notification)
            n.add_action(accept_notification_action,accept_notification_action, accept_notification)
                #logging.debug("Actions in the notification are: %s" % str(actions))
                #time.sleep(5)
            n.show()
            notifications_to_be_shown.remove(notification)
            notifications_already_shown.append(notification)
            time.sleep(notification_showing_interval)
        else:
            if len(feedback_list) != 0:
                logger.debug("Item found in feedback list as: %s" % str(feedback_list[0]))
            time.sleep(notification_showing_interval)

def queue_notification(notification, arrival_time):
    global notification_queue
    notification_queue.append([notification, arrival_time])
    logger.debug("Notification queued.")


def get_noise_level():
    redirect_devnull = open(os.devnull,'w')
    global noise_threshold_passed, noise_threshold, noise_collection_time
    while True:
        total_noise = Popen(['soundmeter', '--collect', '--seconds', noise_collection_time],
                            stdout=PIPE, stderr=redirect_devnull)
        for noise in total_noise.stdout:
            if "avg" in noise:
                noise = int(noise.split(":")[1].rstrip())
                #logger.debug("Noise levels are %d at %d", noise, time.time())
                if noise > noise_threshold:
                    noise_threshold_passed = True
                    if not is_voice_playing():
                        trigger_cost_analysis("Noise Tracker")
                else:
                    noise_threshold_passed = False

        time.sleep(noise_check_interval)


def initialize():
    config = ConfigParser()
    global all_applications_categories

    for desktop_file in glob.glob('/usr/share/applications/*.desktop'):
        config.read(desktop_file)
        application_name = os.path.splitext(os.path.basename(desktop_file))[0]
        try:
            all_applications_categories[application_name] = [c for c in config.get("Desktop Entry", "Categories").lower().split(';') if c]
        except:
            pass # app has no category


def reject_notification(notification, key):
    logging.info("Discard Action invoked for %s " % str(notification['body']))
    notification.close()


def open_notification(notification, key):
    global notifications_already_shown
    try:
        logging.debug("Accept Action invoked for %s " % str(notification))
        body = notification.get_property('body')
        summary = notification.get_property('summary')
        logging.info("The body is: %s" % body)
    except Exception, e:
        logger.debug("Getting accept feedback failed: %s" % e.args[0])

    for item in notifications_already_shown:
        if item['body'] == body or item['summary'] == summary:
            notifications_already_shown.remove(item)
            if "app_name" in item.keys():
                if item['app_name'] != "":
                    sender = item['app_name']
                    # the only difference to accept is the index down here
                    db.persist_feedback(sender, 1)
        notification.close()


def accept_notification(notification, key):
    global notifications_already_shown
    try:
        logging.debug("Accept Action invoked for %s " % str(notification))
        body = notification.get_property('body')
        summary = notification.get_property('summary')
    except Exception, e:
        logger.debug("Getting accept feedback failed: %s" % e.args[0])

    for item in notifications_already_shown:
        if item['body'] == body or item['summary'] == summary:
            notifications_already_shown.remove(item)
            if "app_name" in item.keys():
                if item['app_name'] != "":
                    sender = item['app_name']
                    db.persist_feedback(sender,0)
        notification.close()


def compare_notification_keys(noti1, noti2, key):
    if key in noti1 and key in noti2:
        if noti1[key] == noti2[key]:
            return True
    return False


glib.threads_init()
#logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(message)s')
fh = logging.FileHandler('output.log')
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(ch)
logger.addHandler(fh)

threads = []
initialize()
#notification_collector = threading.Thread(target=listen_to_dbus)
#threading._start_new_thread(show_notification, ())
try:
    db = database.Database(False)
except Exception:
    traceback.print_exc()
    logger.debug("Database initialization failed in Mainthread")
    sys.exit(6)

try:
    notifier = threading.Thread(target=show_notification)
    notifier.daemon = True
    notifier.start()
    threads.append(notifier)
except:
    traceback.print_exc()
    logger.debug("Notification tracker exited with errors.")
    sys.exit(8)

try:
    activity_tracker = threading.Thread(target=window_tracker)
    activity_tracker.daemon = True
    activity_tracker.start()
    threads.append(activity_tracker)
except:
    traceback.print_exc()
    logger.debug("Activity tracker exited with errors")
    sys.exit(9)

try:
    noise_tracker = threading.Thread(target=get_noise_level)
    noise_tracker.daemon = True
    noise_tracker.start()
except:
    traceback.print_exc()
    logger.debug("Noise Tracker exited with errors")

if __name__ == "__main__":
    loop = DBusGMainLoop(set_as_default=True)
    logger.debug("Now initializing Dbus for new notifications")
    session_bus = dbus.SessionBus()
    session_bus.add_match_string(
        "type='method_call',interface='org.freedesktop.Notifications',member='Notify',eavesdrop=true")
    session_bus.add_message_filter(print_notification)
    try:
        glib.MainLoop().run()
    except:
        traceback.print_exc()
        logger.debug("Main loop Quit with errors")
        db.con.close()
        sys.exit(5)
    #logger.debug("Stopped listening for notifications")
