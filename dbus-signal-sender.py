__author__ = 'babak'


#!/usr/bin/env python
import gobject
import sys
import traceback
import dbus
import dbus.mainloop.glib

def handle_reply(msg): print msg
def handle_error(e): print str(e)
def emit_signal():
   # call the emitHelloSignal method
   object.emitHelloSignal(dbus_interface="com.example.TestService")
                          #reply_handler=handle_reply, error_handler=handle_error)
   # exit after waiting a short time for the signal
   gobject.timeout_add(2000, loop.quit)
   return False
def hello_signal_handler(hello_string):
    print ("Received signal (by connecting using remote object) and it says: " + hello_string)
def catchall_signal_handler(*args, **kwargs):
    print ("Caught signal (in catchall handler) ", kwargs['dbus_interface'] + "." + kwargs['member'])
def catchall_hello_signals_handler(hello_string):
    print "Received a hello signal and it says " + hello_string

if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    object = bus.get_object("com.example.TestService","/com/example/TestService/object")
    object.connect_to_signal("HelloSignal", hello_signal_handler, dbus_interface="com.example.TestService", arg0="Hello")
    #lets make a catchall
    bus.add_signal_receiver(catchall_signal_handler, interface_keyword='dbus_interface', member_keyword='member')
    bus.add_signal_receiver(catchall_hello_signals_handler, dbus_interface="com.example.TestService", signal_name="HelloSignal")
    gobject.timeout_add(2000, emit_signal)
    gobject.MainLoop().run()