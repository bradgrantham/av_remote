import flask
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
        # "event_url": flask.url_for('event_create', _external = True),
        # "start_url": flask.url_for('start', _external = True),
        # "test_mode" : test_mode,
        # "offline_mode" : offline_mode,
    }
    content = flask.render_template("start.html", **vars)
    return content.replace("APP.mockup = true", "APP.mockup = false")


@app.route("/set/<what>", methods=['PUT'])
def set_value(what):
    log(INFO, "PUT set " + what)
    log(INFO, "json " + flask.request.data)

    try:
        set_info = json.loads(flask.request.data)
    except ValueError:
        log(DEBUG, flask.request.data)
        fail(400, WARNING, "volume info couldn't be decoded as JSON")

    if what == 'volume':
        print "volume to " + set_info['value']
    else:
        fail(400, WARNING, "unknown thing " + what + " in set value")

    return json.dumps({'success':True})


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

