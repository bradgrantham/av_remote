import flask
import traceback
import json
import datetime
import os
import threading
import subprocess
import socket
import errno
import time

import rabbithole_av

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
        "startup_status": json.dumps(rabbithole_av.get_current_status()),
        # "start_url": flask.url_for('start', _external = True),
        # "test_mode" : test_mode,
        # "offline_mode" : offline_mode,
    }
    content = flask.render_template("start.html", **vars)
    return content.replace("APP.mockup = true", "APP.mockup = false")


@app.route("/status", methods=['GET'])
def get_status():
    log(INFO, "GET status")

    return json.dumps(rabbithole_av.get_current_status())


@app.route("/set/<what>", methods=['PUT'])
def set_value(what):

    log(INFO, "PUT set " + what)
    log(INFO, "json " + flask.request.data)

    try:
        set_info = json.loads(flask.request.data)
    except ValueError:
        log(DEBUG, flask.request.data)
        fail(400, WARNING, "volume info couldn't be decoded as JSON")

    value = set_info['value']

    if what == 'volume':
        rabbithole_av.set_volume(int(value))
    elif what == 'muting':
        rabbithole_av.set_muting(rabbithole_av.power_to_bool[value])
    elif what == 'video_power':
        # XXX set video power
        pass
    elif what == 'receiver_power':
        rabbithole_av.set_receiver_power(rabbithole_av.power_to_bool[value])
    elif what == 'mode':
        if value not in rabbithole_av.mode_string_to_id:
            fail(400, WARNING, "unknown input mode " + value + " in set value")
        else:
	    # XXX I'm comfortable with REST "what" not being the same
	    # as the "what" passed on.  Maybe it's okay.
            rabbithole_av.set_receiver_input(rabbithole_av.mode_string_to_id[value])
    elif what == 'replace_audio':
        if value not in ("on", "off"):
            fail(400, WARNING, "unknown audio replace setting " + value + " in set value")
        else:
	    # XXX I'm comfortable with this little bit of application logic in here,
	    # should be in receiver_worker, probably.
	    audio = rabbithole_av.receiver_audio_to_id["hdmi"]
	    if value == "on":
		audio = rabbithole_av.receiver_audio_to_id["analog"]
            rabbithole_av.set_receiver_audio(audio)
    else:
        fail(400, WARNING, "unknown thing " + what + " in set value")

    return json.dumps(rabbithole_av.get_current_status())


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

    port = 5066

    if ("VISIBLEIP" in os.environ):
        app.run(port=port, host="0.0.0.0", threaded=True)
    else:
        app.run(port=port, threaded=True)
