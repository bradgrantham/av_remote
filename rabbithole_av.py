import json
import os
import errno
# sudo easy_install onkyo-eiscp
import eiscp
import time
import atexit
import threading

#############################################################################
# A/V receiver control logic

power_to_bool = {
    "standby,off" : False,
    "off" : False,
    "on" : True,
}

bool_to_power = {
    False: "off",
    True: "on",
}

receiver_audio_to_id = {
    "analog" : 0,
    "hdmi" : 1,
}

receiver_input_to_id = {
    "dvd,bd,dvd" : 1,
    "video2,cbl,sat" : 2,
    "fm" : 3,
    "bluetooth" : 4,
}

mode_string_to_id = {
    "ChromeCast Audio" : 0,
    "ChromeCast Video" : 1,
    "Table HDMI" : 2,
    "FM Radio" : 3,
    "Bluetooth" : 4,
    "Other" : 5,
}

mode_id_to_string = {}

for (name, id) in mode_string_to_id.iteritems():
    mode_id_to_string[id] = name

mode_id_to_receiver_input = {}
for (input, id) in receiver_input_to_id.iteritems():
    mode_id_to_receiver_input[id] = input

mode_id_to_receiver_audio = {}
for (audio, id) in receiver_audio_to_id.iteritems():
    mode_id_to_receiver_audio[id] = audio

# These are the Onkyo numbers on the display that correspond to min and max.
receiver_volume_min = 0
receiver_volume_max = 50
receiver_volume_range = receiver_volume_max - receiver_volume_min

current_receiver_power = False

ERROR=1
WARNING=2
INFO=3
DEBUG=4
VERBOSE=5

def log(level, string):
    if False:
        print level, string

def send_command_to_receiver(s):
    global receiver

    try:
	return receiver.command(s)
    except Exception, e:
        print "Exception, reconnecting: " + str(e)
	# maybe Receiver power-cycled - try to open connection again
	log(ERROR, "unexpected condition caused receiver command to fail, trying to reconnect")
	# receiver.disconnect()
	tries = 0
	while tries <= 5:
	    tries = tries + 1
	    try:
		receiver = eiscp.eISCP("192.168.1.151")
                # Argh - creating receiver object doesn't actually connect,
                # so send power query to connect and fail if necessary.
		power_test = receiver.command("system-power=query")
		if receiver and power_test:
		    log(ERROR, "connecting to receiver succeeded, sending command")
		    return receiver.command(s)
	    except:
		pass
	    log(ERROR, "connecting to receiver failed, try number %d" % tries)

    receiver = None
    log(ERROR, "unexpected condition caused receiver command to fail repeatedly")
    return None

def get_receiver_state():
    global current_audio
    global current_receiver_power
    global current_volume
    global current_muting
    global current_mode
    global eiscp_lock
    global receiver

    try:
	then = time.clock()
	with eiscp_lock:
	    system_power_query = send_command_to_receiver("system-power=query")
	    audio_muting_query = send_command_to_receiver("audio-muting=query")
	    system_volume_query = send_command_to_receiver("volume=query")
	    input_selector_query = send_command_to_receiver("input-selector=query")
	    audio_selector_query = send_command_to_receiver("audio-selector=query")

	current_receiver_power = (system_power_query[1] == 'on')

	current_muting = (audio_muting_query[1] == 'on')

	if isinstance(input_selector_query[1], tuple):
	    input_selector_string = ",".join(input_selector_query[1])
	else:
	    input_selector_string = input_selector_query[1]
	current_mode = receiver_input_to_id.get(input_selector_string, len(receiver_input_to_id))

	current_volume = (system_volume_query[1] - receiver_volume_min) * 100 / receiver_volume_range

	if isinstance(audio_selector_query[1], tuple):
	    audio_selector_string = ",".join(audio_selector_query[1])
	else:
	    audio_selector_string = audio_selector_query[1]
	current_audio = receiver_audio_to_id.get(audio_selector_string, len(receiver_audio_to_id))
	log(INFO, "audio_selector_string = %s, current_audio = %d" % (audio_selector_string, current_audio))
	now = time.clock()
	log(INFO, "time to get and parse state: %f" % (now - then))
    except:
	current_receiver_power = False
        raise

def set_receiver_audio(id):
    global current_audio
    current_audio = id
    receiver_status["replace_audio"] = bool_to_power[current_audio == 0],
    command = "audio-selector=%s" % mode_id_to_receiver_audio[id]
    with eiscp_lock:
        send_command_to_receiver(command)
    log(INFO, "set_receiver_audio %d" % (current_audio))
    log(INFO, "set_receiver_audio command %s" % (command))

def set_receiver_input(id):
    global current_mode
    global current_audio
    current_mode = id
    receiver_status["mode"] = mode_id_to_string[current_mode],
    input_command = "input-selector=%s" % mode_id_to_receiver_input[id]
    audio_command = "audio-selector=%s" % mode_id_to_receiver_audio[current_audio]
    with eiscp_lock:
        send_command_to_receiver(input_command)
	send_command_to_receiver(audio_command)

def set_receiver_power(value):
    global current_receiver_power
    current_receiver_power = value
    current_muting = value
    receiver_status["receiver_power"] = bool_to_power[current_receiver_power]
    command = "system-power=%s" % bool_to_power[value]
    with eiscp_lock:
	send_command_to_receiver(command)

def set_muting(value):
    global current_muting
    current_muting = value
    receiver_status["muting"] = bool_to_power[current_muting]
    command = "audio-muting=%s" % bool_to_power[value]
    with eiscp_lock:
	send_command_to_receiver(command)

def set_volume(value):
    global current_volume
    current_volume = value
    receiver_status["volume"] = current_volume
    volume = current_volume * receiver_volume_range / 100 + receiver_volume_min
    command = "volume=%d" % volume
    with eiscp_lock:
	send_command_to_receiver(command)

# up is True for up or False for down
def nudge_volume(up):
    global current_volume
    # print "nudge volume %s" % {True: 'up', False: 'down'}[direction]
    if direction:
        volume = math.min(100, volume + 1)
    else:
        volume = math.max(0, volume - 1)
    command = "volume=%s" % {True: 'level-up', False: 'level-down'}[direction]
    with eiscp_lock:
	send_command_to_receiver(command)

def get_current_status():
    global current_audio
    global current_receiver_power
    global current_volume
    global current_muting
    global current_mode
    global eiscp_lock
    global receiver

    get_receiver_state()
    status = {
	"connected" : bool_to_power[(receiver is not None)],
        "volume" : current_volume,
        "muting" : bool_to_power[current_muting],
        "receiver_power" : bool_to_power[current_receiver_power],
        "mode" : mode_id_to_string[current_mode],
        "replace_audio" : bool_to_power[current_audio == 0],
    }
    return status

@atexit.register
def shutdown():
    global receiver

    receiver.disconnect()

eiscp_lock = threading.Lock()

receiver = eiscp.eISCP("192.168.1.151")
receiver_status = get_current_status()

