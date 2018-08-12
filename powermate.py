#!/usr/bin/env python

import select
import os
import fcntl
import struct
import exceptions

import rabbithole_av

input_event_struct = "@llHHi"
input_event_size = struct.calcsize(input_event_struct)

EVENT_UNKNOWN = 0
EVENT_BUTTON_PRESS = 1
EVENT_RELATIVE_MOTION = 2
RELATIVE_AXES_DIAL = 7
BUTTON_MISC = 0x100

def report(x):
    sys.stderr.write(x + "\n")

class Event(object):
    def __init__(self, sec, usec, type, code, value):
        self.sec = sec
        self.usec = usec
        self.type = type
        self.code = code
        self.value = value

    def __str__(self):
        return "%s %d" % (self.type_to_str(self.type), self.value)

    def type_to_str(self, type):
        if type == EVENT_BUTTON_PRESS:
            return "BUTTON"
        elif type == EVENT_RELATIVE_MOTION:
            return "MOTION"
        else:
            return "UNKNOWN(%d)" % type

class PowerMate:
    def __init__(self, filename = None):
        self.handle = -1
        if filename:
            if not self.OpenDevice(filename):
                raise exceptions.RuntimeError, 'Unable to find powermate'
        else:
            ok = 0
            for d in range(0, 16):
                if self.OpenDevice("/dev/input/event%d" % d):
                    ok = 1
                    break
            if not ok:
                raise exceptions.RuntimeError, 'Unable to find powermate'
        self.poll = select.poll()
        self.poll.register(self.handle, select.POLLIN)
        self.event_queue = [] # queue used to reduce kernel/userspace context switching

    def __del__(self):
        if self.handle >= 0:
            self.poll.unregister(self.handle)
            os.close(self.handle)
            self.handle = -1
            del self.poll
            
    def OpenDevice(self, filename):
        try:
            self.handle = os.open(filename, os.O_RDWR)
            if self.handle < 0:
                return 0
            name = fcntl.ioctl(self.handle, 0x80ff4506, chr(0) * 256) # read device name
            name = name.replace(chr(0), '')
            if name == 'Griffin PowerMate' or name == 'Griffin SoundKnob':
                fcntl.fcntl(self.handle, fcntl.F_SETFL, os.O_NDELAY)
                return 1
            os.close(self.handle)
            self.handle = -1
            return 0
        except exceptions.OSError:
            return 0

    def WaitForEvent(self, timeout): # timeout in seconds
        if len(self.event_queue) > 0:
            return self.event_queue.pop(0)
        if self.handle < 0:
            return None
        r = self.poll.poll(int(timeout*1000))
        if len(r) == 0:
            return None
        return self.GetEvent()
        
    def GetEvent(self): # only call when descriptor is readable
        if self.handle < 0:
            return None
        try:
            data = os.read(self.handle, input_event_size * 32)
            while data != '':
                t = struct.unpack(input_event_struct, data[0:input_event_size])
                event = Event(t[0], t[1], t[2], t[3], t[4])
                self.event_queue.append(event)
                data = data[input_event_size:]
            return self.event_queue.pop(0)
        except exceptions.OSError, e: # Errno 11: Resource temporarily unavailable
            #if e.errno == 19: # device has been disconnected
            #    report("PowerMate disconnected! Urgent!");
            return None

    def SetLEDState(self, static_brightness, pulse_speed, pulse_table, pulse_on_sleep, pulse_on_wake):
        static_brightness &= 0xff;
        if pulse_speed < 0:
            pulse_speed = 0
        if pulse_speed > 510:
            pulse_speed = 510
        if pulse_table < 0:
            pulse_table = 0
        if pulse_table > 2:
            pulse_table = 2
        pulse_on_sleep = not not pulse_on_sleep # not not = convert to 0/1
        pulse_on_wake  = not not pulse_on_wake
        magic = static_brightness | (pulse_speed << 8) | (pulse_table << 17) | (pulse_on_sleep << 19) | (pulse_on_wake << 20)
        data = struct.pack(input_event_struct, 0, 0, 0x04, 0x01, magic)
        os.write(self.handle, data)

def main():
    p = PowerMate()

    while True:
        # print "Waiting..."
        e = p.WaitForEvent(1)
        if e is None:
            pass
            # print "Timeout"
        else:
            if e.type == EVENT_BUTTON_PRESS:
                # Toggle mute.
                if e.value:
                    new_muting = not rabbithole_av.current_muting
                    print "Setting muting to " + str(new_muting)
                    rabbithole_av.set_muting(new_muting)
                    print "Done muting"
            elif e.type == EVENT_RELATIVE_MOTION:
                # Change volume.
                delta = e.value
                new_value = rabbithole_av.current_volume + delta
                new_value = min(max(new_value, 0), 100)
                print "Setting volume to %d" % new_value
                rabbithole_av.set_volume(new_value)
                print "Done setting volume"
            elif e.type == EVENT_UNKNOWN:
                # Ignore.
                pass
            else:
                # Unknown command.
                print "Unknown command: " + str(e)

if __name__ == "__main__":
    main()
