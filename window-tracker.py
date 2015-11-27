from subprocess import PIPE, Popen
import time

title = ''
root_check = ''

while True:
    time.sleep(0.6)
    root = Popen(['xprop', '-root'],  stdout=PIPE)

    if root.stdout != root_check:
        root_check = root.stdout

        for i in root.stdout:
            if '_NET_ACTIVE_WINDOW(WINDOW):' in i:
                id_ = i.split()[4]
                id_w = Popen(['xprop', '-id', id_], stdout=PIPE)

        for j in id_w.stdout:
            if '_NET_WM_PID' in j:
                if title != j.split()[2]:
                    title = j.split()[2]
                    print "current window pid: %s" % title
                    pid = Popen(['ps', '-p',  title, '-o' ,'comm='], stdout=PIPE)
        for z in pid.stdout:
            pid =  z
