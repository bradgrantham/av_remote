
import sys
import termios
import tty

import rabbithole_av

# k    i
# w    ?
# s    a
def handle_button(ch):
    sys.stderr.write("Handling key: \"%c\" (ASCII %d)\r\n" % (ch, ord(ch)))
    if ch == 'k':
        # Switch audio to HDMI.
        rabbithole_av.set_receiver_audio(rabbithole_av.receiver_audio_to_id["hdmi"])
    elif ch == 'i':
        # Switch HDMI to table.
        sys.stderr.write("Table HDMI\r\n")
        rabbithole_av.set_receiver_input(rabbithole_av.mode_string_to_id["Table HDMI"])
    elif ch == 'w':
        # Switch audio to ChromeCast Audio.
        rabbithole_av.set_receiver_audio(rabbithole_av.receiver_audio_to_id["analog"])
    elif ch == '?':
        pass
    elif ch == 's':
        pass
    elif ch == 'a':
        # Switch HDMI to ChromeCast.
        sys.stderr.write("ChromeCast\r\n")
        rabbithole_av.set_receiver_input(rabbithole_av.mode_string_to_id["ChromeCast Video"])
    else:
        sys.stderr.write("Unknown key: \"%c\" (ASCII %d)\r\n" % (ch, ord(ch)))

def main():
    stdin_fd = sys.stdin.fileno()
    old_stdin_tty = termios.tcgetattr(stdin_fd)

    try:
        # Put terminal in raw mode.
	tty.setraw(stdin_fd)

	while True:
	    ch = sys.stdin.read(1)
	    if ord(ch) == 3:
		sys.stdout.write("\r\n^C\r\n")
		return
            handle_button(ch)
    finally:
        # Restore terminal.
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_stdin_tty)

if __name__ == "__main__":
    main()
