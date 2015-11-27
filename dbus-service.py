__author__ = 'babak'

#!/usr/bin/env python
import dbus
import dbus.service

class SomeObject(dbus.service.Object):
    def __init__(self):
        self.session_bus = dbus.SessionBus()
        name = dbus.service.BusName("org.freedesktop.Notifications", bus=self.session_bus)
        #name = dbus.service.BusName("com.example.SampleService", bus=self.session_bus)
        dbus.service.Object.__init__(self, name, '/SomeObject')
    @dbus.service.method("com.example.SampleInterface", in_signature='s', out_signature='as')
    def HelloWorld(self, hello_message):
        print(hello_message)
        return ["Hello", "from example-service.py", "with unique name", self.session_bus.get_unique_name()]
    @dbus.service.method("com.example.SampleInterface", in_signature='', out_signature='')
    def Exit(self):
        loop.quit()
if __name__ == '__main__':
    # using glib
    import dbus.mainloop.glib
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    import gobject
    loop = gobject.MainLoop()
    object = SomeObject()
    loop.run()