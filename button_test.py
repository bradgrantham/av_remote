
# Control the AV system using GPIO buttons.

import time
import Queue
import RPi.GPIO as GPIO

# How often to poll the receiver's status, in seconds.
POLL_PERIOD_S = 1

# BOARD pin numbers.
SW1 = 7
SW2 = 11
SW3 = 13
SW4 = 15
SW5 = 19
SW6 = 21
LED1 = 23
LED2 = 29
LED3 = 31
LED4 = 33
LED5 = 35
LED6 = 37

# Lists for iteration.
SW_LIST = [ SW1, SW2, SW3, SW4, SW5, SW6 ]
LED_LIST = [ LED1, LED2, LED3, LED4, LED5, LED6 ]

# Queue to communicate between interrupt thread and main thread. Element is
# BOARD pin number of button that was pressed.
g_switch_event = Queue.Queue()

# Called on main thread when a switch is pressed. "sw" is one of the SW? values.
def handle_switch_event(sw):

    print "Got switch %d" % (sw)

    # Update state right away.
    # update_led_state()

def main():
    # Use the numbering on the header.
    GPIO.setmode(GPIO.BOARD)

    # Configure the LED pins.
    for led in LED_LIST:
        print led
        GPIO.setup(led, GPIO.OUT)

    # Configure the switch pins.
    for sw in SW_LIST:
        print sw
        GPIO.setup(sw, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Put pin number into a queue to be picked up by the main thread.
        GPIO.add_event_detect(sw, GPIO.FALLING, callback=g_switch_event.put, bouncetime=300)

    for l in xrange(0, 6):
        GPIO.output(LED_LIST[l], True)
        time.sleep(.3);
        GPIO.output(LED_LIST[l], False)

    while True:
        for l in xrange(0, 6):
            GPIO.output(LED_LIST[l], True)
        time.sleep(.5)
        for l in xrange(0, 6):
            GPIO.output(LED_LIST[l], False)
        time.sleep(.5)


    print "Ready"
    while True:
        try:
            # Wait for switch event in queue.
            print "Polling"
            sw = g_switch_event.get(True, POLL_PERIOD_S)
            handle_switch_event(sw)
        except Queue.Empty:
            # Update our LEDs.
            # update_led_state()
            pass

if __name__ == "__main__":
    main()
