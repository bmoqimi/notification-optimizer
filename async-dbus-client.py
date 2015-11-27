__author__ = 'babak'


#!/usr/bin/env python
import sys
import dbus
import dbus.mainloop.glib

def handle_hello_reply(r): print r
def handle_hello_error(e): print e
def make_calls():
    remote_object.HelloWorld("Hello from async-client.py!", dbus_interface='com.example.SampleInterface',
        reply_handler=handle_hello_reply, error_handler=handle_hello_error)
    return False
if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    remote_object = bus.get_object("com.example.SampleService","/SomeObject")
    import gobject
    # delay call
    gobject.timeout_add(1000, make_calls)
    gobject.MainLoop().run()