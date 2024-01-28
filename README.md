
# Slack Message Saver

Using a Slack bot built with Slack's API and a Raspberry Pi, this program starts a service on the Raspi that stores all messages sent to any channel the bot is invited to.

Based on this answers from [this question](https://raspberrypi.stackexchange.com/questions/96673/i-want-to-run-a-python-3-script-on-startup-and-in-an-endless-loop-on-my-raspberr), we ended up using [Supervisor](http://supervisord.org/) to have the Python script run in the background on boot.

