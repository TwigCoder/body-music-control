# Music Body Controller

A visualization tool that uses your webcam feed to let you control your music with gestures. Built with the superior language Python.

You may need to tune some of the treshholds and margins to get the best results. For example, if tilting your head does not change the volume, change `HEAD_TILT_THRESHOLD` (lower values means greater sensitivity).

When running the program, use `sudo python3.11 app.py` to avoid permission errors.

NOTE: This has been verified to work on MacOS. Linux and Windows are supported, but those platforms have not been tested. Please try it out and submit a PR if it does not work!

## What it does
- Renders your face and arms in real-time
- Control your music player with natural gestures:
  - Raise both arms to play/pause
  - Move both hands to right edge to skip track
  - Move both hands to left edge to go back a track
  - Tilt head left/right to adjust volume
