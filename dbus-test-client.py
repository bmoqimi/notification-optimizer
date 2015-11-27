__author__ = 'babak'


#!/usr/bin/env python
import sys
from traceback import print_exc
import dbus

def main():
    bus = dbus.SessionBus()
    remote_object = bus.get_object("com.example.SampleService", "/SomeObject")
    print ' '.join(remote_object.HelloWorld("Hello from example-client.py!", dbus_interface = "com.example.SampleInterface"))
    # ... or create an Interface wrapper for the remote object
    iface = dbus.Interface(remote_object, "com.example.SampleInterface")
    print iface.HelloWorld("Hello from example-client.py!")
    # introspection is automatically supported
    print remote_object.Introspect(dbus_interface="org.freedesktop.DBus.Introspectable")
    if sys.argv[1:] == ['--exit-service']:
        iface.Exit()

if __name__ == '__main__':
    main()