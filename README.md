An A/V remote for the Pioneer VSX-S520 A/V Receiver and one or two Viewsonic CDE4302 commercial monitors 

Goals:
* Mobile form factor web UI
* Turn everything on or off
* Set A/V volume and input
* Mute audio
* Python/Flask backend communicates using Pioneer IP and Viewsonic RS232 protocols

Current status:
* All Onkyo EISCP Receiver operations actually work
* No Viewsonic power on/off yet
* Needs mobile-friendly stylesheet
* Needs handling of lost EISCP connections
* Isn't really interactive
* "Chromecast Audio" checkbox doesn't reflect current status properly

One notable item about this remote control is that I can select the HDMI audio stream or Analog input #1 can be selected while selecting an HDMI video input.  This allows me to display a Chromecast or the table HDMI cable while playing a Chromecast Audio.  So we can cast a desktop to the screen to review code or images while casting Spotify to audio.  I can switch back to listen to the audio from the desktop, or to cast Youtube to the Chromecast.
