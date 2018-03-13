import flask
import traceback
import json
import datetime
import os
import threading
import subprocess
import socket
import errno
import eiscp
import time

#############################################################################
# HTTP half
#     * serves REST
#     * adds PUTs to request queue
#     * sends status in response to GETs
# Receiver half
#     * reads queue and sends commands to Onkyo Receiver
#     * reads Onkyo status and sets global status
# Conversion between REST site-specific requests and Onkyo general Receiver requests is
# performed by Receiver half.


# App runtime configuration

logfilename = os.environ.get('LOG_NAME', "log.txt")
logfile = open(logfilename, "w", 0)
loglock = threading.Lock()

#############################################################################
# datetime utility

def tosql(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def get_time_string(add_seconds = 0):
    return tosql(datetime.datetime.utcnow() + datetime.timedelta(seconds = add_seconds))


#############################################################################
# log/debugging utility

ERROR=1
WARNING=2
INFO=3
DEBUG=4
VERBOSE=5

severity_clamp = int(os.environ.get('LOG_LEVEL', str(WARNING)))

def get_caller_info(stack):
    sequence = stack[-2][2] + ":" + str(stack[-2][1])
    while len(stack) > 2 and stack[-3][2] != 'dispatch_request':
        sequence = stack[-3][2] + ":" + str(stack[-3][1]) + "|" + sequence
        del stack[-3]
    return sequence


def log(severity, what):
    datetime = get_time_string()
    if severity <= severity_clamp:
        with loglock:
            print >>logfile, '"%s", "%s", %d, "%s"' % (get_time_string(), get_caller_info(traceback.extract_stack()), severity, what)


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
    "video2,cbl,sat" : 0,
    "dvd,bd,dvd" : 1,
    "video3,game/tv,game,game1" : 2,
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

current_video_power = True # XXX mockup

# These are the Onkyo numbers on the display that correspond to min and max.
receiver_volume_min = 0
receiver_volume_max = 50
receiver_volume_range = receiver_volume_max - receiver_volume_min

def get_receiver_state():
    global current_audio
    global current_video_power
    global current_receiver_power
    global current_volume
    global current_muting
    global current_mode
    global main_lock

    with main_lock:
        system_power_query = receiver.command("system-power=query")
        audio_muting_query = receiver.command("audio-muting=query")
        system_volume_query = receiver.command("volume=query")
        input_selector_query = receiver.command("input-selector=query")
        audio_selector_query = receiver.command("audio-selector=query")

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

def send_volume():
    global current_volume
    global send_volume_scheduled
    with main_lock:
        volume = current_volume * receiver_volume_range / 100 + receiver_volume_min
        command = "volume=%d" % volume
        print command
	receiver.command(command)
        send_volume_scheduled = False

def set_receiver_audio(id):
    global current_audio
    current_audio = id
    command = "audio-selector=%s" % mode_id_to_receiver_audio[id]
    print command
    with main_lock:
        receiver.command(command)
    log(INFO, "set_receiver_audio %d" % (current_audio))
    log(INFO, "set_receiver_audio command %s" % (command))

def set_receiver_input(id):
    global current_mode
    global current_audio
    current_mode = id
    input_command = "input-selector=%s" % mode_id_to_receiver_input[id]
    print input_command
    audio_command = "audio-selector=%s" % mode_id_to_receiver_audio[current_audio]
    print audio_command
    with main_lock:
        receiver.command(input_command)
        receiver.command(audio_command)

def set_receiver_power(value):
    global current_receiver_power
    current_receiver_power = value
    command = "system-power=%s" % bool_to_power[value]
    print command
    with main_lock:
        receiver.command(command)

def set_muting(value):
    global current_muting
    current_muting = value
    command = "audio-muting=%s" % bool_to_power[value]
    print command
    with main_lock:
        receiver.command(command)

def set_volume(value):
    global current_volume
    global send_volume_scheduled
    print "set volume to %d and requested send" % value
    with main_lock:
        current_volume = value
        if not send_volume_scheduled:
            t = threading.Timer(.1, send_volume)
            t.start()
            send_volume_scheduled = True
    
def get_current_status():
    get_receiver_state()
    status = {
        "volume" : current_volume,
        "video_power" : bool_to_power[current_video_power],
        "receiver_power" : bool_to_power[current_receiver_power],
        "muting" : bool_to_power[current_muting],
        "mode" : mode_id_to_string[current_mode],
        "replace_audio" : bool_to_power[current_audio == 0],
    }
    log(INFO, "current audio %d, string %s" % (current_audio, bool_to_power[current_audio == 0]))
    return status

def receiver_worker():
    global receiver_thread_stop
    global receiver_status
    global receiver
    receiver = eiscp.eISCP("192.168.1.151")
    log(INFO, "receiver worker")
    while not receiver_thread_stop:
	log(INFO, "receiver worker loop")
	s = get_current_status()
	with main_lock:
	    receiver_status = s
	# drain queue
	time.sleep(2)
    receiver.disconnect()

#############################################################################
# fail using Flask path

def fail(status, severity, what):
    datetime = get_time_string()
    if severity <= severity_clamp:
        with loglock:
            print >>logfile, '"%s", "%s", %d, %d because "%s"' % (get_time_string(), get_caller_info(traceback.extract_stack()), severity, status, what)
    flask.abort(status)


app = flask.Flask(__name__)


@app.route("/", methods=['GET'])
def root():
    vars = {
        "startup_status": json.dumps(receiver_status),
        # "start_url": flask.url_for('start', _external = True),
        # "test_mode" : test_mode,
        # "offline_mode" : offline_mode,
    }
    content = flask.render_template("start.html", **vars)
    return content.replace("APP.mockup = true", "APP.mockup = false")


@app.route("/status", methods=['GET'])
def get_status():
    log(INFO, "GET status")

    with main_lock:
	s = receiver_status
    return json.dumps(s)


@app.route("/set/<what>", methods=['PUT'])
def set_value(what):

    global current_muting
    global current_video_power
    global current_receiver_power
    global current_mode

    log(INFO, "PUT set " + what)
    log(INFO, "json " + flask.request.data)

    try:
        set_info = json.loads(flask.request.data)
    except ValueError:
        log(DEBUG, flask.request.data)
        fail(400, WARNING, "volume info couldn't be decoded as JSON")

    value = set_info['value']

    if what == 'volume':
        set_volume(int(value))
    elif what == 'muting':
        set_muting(power_to_bool[value])
    elif what == 'video_power':
        # XXX set video power
        pass
    elif what == 'receiver_power':
        set_receiver_power(power_to_bool[value])
    elif what == 'mode':
        if value not in mode_string_to_id:
            fail(400, WARNING, "unknown input mode " + value + " in set value")
        else:
            set_receiver_input(mode_string_to_id[value])
    elif what == 'replace_audio':
        if value not in ("on", "off"):
            fail(400, WARNING, "unknown audio replace setting " + value + " in set value")
        else:
	    audio = receiver_audio_to_id["hdmi"]
	    if value == "on":
		audio = receiver_audio_to_id["analog"]
            set_receiver_audio(audio)
    else:
        fail(400, WARNING, "unknown thing " + what + " in set value")

    return json.dumps(receiver_status)


def shutdown_server():
    func = flask.request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    receiver_thread_stop = True
    receiver_thread.join()
    func()


@app.route('/shutdown', methods=['POST'])
def shutdown():
    shutdown_server()
    return 'Server shutting down...'


#############################################################################
# Main

if __name__ == "__main__":

    main_lock = threading.Lock()
    send_volume_scheduled = False

    receiver_thread_stop = False
    print "start thread"
    receiver_thread = threading.Thread(target = receiver_worker)
    receiver_thread.start()

    port = 5066

    try:
	if ("VISIBLEIP" in os.environ):
	    app.run(debug = False, port=port, host="0.0.0.0", threaded=True)
	else:
	    app.run(debug = False, port=port, threaded=True)
    # except KeyboardInterrupt:
        # print "interrupt received, stopping"
    finally:
	# clean up
	print "shutting down"
	receiver_thread_stop = True
	receiver_thread.join()
