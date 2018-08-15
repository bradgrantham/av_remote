
import Queue
import GPIO
import rabbithole_av

# How often to poll the receiver's status, in seconds.
POLL_PERIOD_S = 1

# BOARD pin numbers.
SW1 = 3
SW2 = 5
SW3 = 7
SW4 = 11
SW5 = 13
SW6 = 15
LED1 = 19
LED2 = 21
LED3 = 23
LED4 = 29
LED5 = 31
LED6 = 33

# Lists for iteration.
SW_LIST = [ SW1, SW2, SW3, SW4, SW5, SW6 ]
LED_LIST = [ LED1, LED2, LED3, LED4, LED5, LED6 ]

# Assignments to functions. Value is index in lists above.
VIDEO_CHROMECAST = 0
VIDEO_TABLE = 1
AUDIO_HDMI = 2
AUDIO_ANALOG = 3

# Names in the rabbithole_av module.
VIDEO_CHROMECAST_NAME = "ChromeCast Video"
VIDEO_TABLE_NAME = "Table HDMI"
AUDIO_HDMI_NAME = "hdmi"
AUDIO_ANALOG_NAME = "analog"

# Queue to communicate between interrupt thread and main thread. Element is
# BOARD pin number of button that was pressed.
g_switch_event = Queue.Queue()

# Update the LEDs for video output.
def update_video_led(video_mode):
    GPIO.output(LED_LIST[VIDEO_CHROMECAST], audio_mode == VIDEO_CHROMECAST_NAME)
    GPIO.output(LED_LIST[VIDEO_TABLE], audio_mode == VIDEO_TABLE_NAME)

# Update the LEDs for audio output.
def update_audio_led(audio_mode):
    GPIO.output(LED_LIST[AUDIO_HDMI], audio_mode == AUDIO_HDMI_NAME)
    GPIO.output(LED_LIST[AUDIO_ANALOG], audio_mode == AUDIO_ANALOG_NAME)

# Fetch the current state from the receiver and update LEDs.
def update_led_state():
    rabbithole_av.get_receiver_state()
    update_video_led(rabbithole_av.mode_id_to_string[rabbithole_av.current_mode])
    update_audio_led(rabbithole_av.mode_id_to_receiver_audio[rabbithole_av.current_audio])

# Called on main thread when a switch is pressed. "sw" is one of the SW? values.
def handle_switch_event(sw):
    try:
        index = SW_LIST.index(sw)
    except ValueError:
        print "Switch not found in list: %d" % sw
        return

    print "Got switch %d, mapping to index %d" % (sw, index)

    if index == VIDEO_CHROMECAST:
        rabbithole_av.set_receiver_input(rabbithole_av.mode_string_to_id[VIDEO_CHROMECAST_NAME])
    elif index == VIDEO_TABLE:
        rabbithole_av.set_receiver_input(rabbithole_av.mode_string_to_id[VIDEO_TABLE_NAME])
    elif index == AUDIO_HDMI:
        rabbithole_av.set_receiver_audio(rabbithole_av.receiver_audio_to_id[AUDIO_HDMI_NAME])
    elif index == AUDIO_ANALOG:
        rabbithole_av.set_receiver_audio(rabbithole_av.receiver_audio_to_id[AUDIO_ANALOG_NAME])
    else:
        print "Index function not found: %d" % index

    # Update state right away.
    update_led_state()

def main():
    # Use the numbering on the header.
    GPIO.setmode(GPIO.BOARD)

    # Configure the LED pins.
    for led in LED_LIST:
        GPIO.setup(led, GPIO.OUT)

    # Configure the switch pins.
    for sw in SW_LIST:
        GPIO.setup(sw, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Put pin number into a queue to be picked up by the main thread.
        GPIO.add_event_detect(sw, GPIO.FALLING, callback=g_switch_event.put, bouncetime=300)

    while True:
        try:
            # Wait for switch event in queue.
            sw = g_switch_event.get(True, POLL_PERIOD_S)
            handle_switch_event(sw)
        except Queue.Empty:
            # Update our LEDs.
            update_led_state()

if __name__ == "__main__":
    main()
