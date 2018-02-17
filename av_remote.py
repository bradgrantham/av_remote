import flask
import traceback
import json
import datetime
import os
import threading
import subprocess
import socket
import errno

logfilename = os.environ.get('LOG_NAME', "log.txt")
logfile = open(logfilename, "w", 0)
loglock = threading.Lock()

power_to_bool = {
    "off" : False,
    "on" : True,
}
bool_to_power = {
    False: "off",
    True: "on",
}

mode_string_to_id = {
    "ChromeCast Audio" : 0,
    "ChromeCast Video" : 1,
    "Table HDMI" : 2,
    "FM Radio" : 3,
}

mode_id_to_string = {}

for (name, id) in mode_string_to_id.iteritems():
    mode_id_to_string[id] = name

current_mode = 2; # XXX mockup
current_volume = 50;
current_video_power = True;
current_receiver_power = True;
current_muting = False; # XXX special value overrides volume...?
    
def get_current_status():
    status = {
        "volume" : current_volume,
        "video_power" : bool_to_power[current_video_power],
        "receiver_power" : bool_to_power[current_receiver_power],
        "muting" : bool_to_power[current_muting],
        "mode" : mode_id_to_string[current_mode],
    }
    return status


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
        "startup_status": json.dumps(get_current_status()),
        # "start_url": flask.url_for('start', _external = True),
        # "test_mode" : test_mode,
        # "offline_mode" : offline_mode,
    }
    content = flask.render_template("start.html", **vars)
    return content.replace("APP.mockup = true", "APP.mockup = false")


@app.route("/status", methods=['GET'])
def get_status():
    log(INFO, "GET status")

    return json.dumps(get_current_status())


@app.route("/set/<what>", methods=['PUT'])
def set_value(what):

    global current_volume
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
        current_volume = int(value)
        # set volume and verify it on receiver
    elif what == 'muting':
        current_muting = power_to_bool[value]
        # XXX set muting
    elif what == 'video_power':
        current_video_power = power_to_bool[value]
        # XXX set video power
    elif what == 'receiver_power':
        current_receiver_power = power_to_bool[value]
        # XXX set receiver power
    elif what == 'mode':
        current_mode = mode_string_to_id[value]
        # XXX set video power
    else:
        fail(400, WARNING, "unknown thing " + what + " in set value")

    return json.dumps(get_current_status())


def shutdown_server():
    func = flask.request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()


@app.route('/shutdown', methods=['POST'])
def shutdown():
    shutdown_server()
    return 'Server shutting down...'


#############################################################################
# Main

if __name__ == "__main__":

    if ("VISIBLEIP" in os.environ):
        app.run(debug = True, port=5060, host="0.0.0.0")
    else:
        app.run(debug = True, port=5060)

