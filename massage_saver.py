# activate the venv for the script using source bin/.slack_bot/activate

import os
import json
import gzip
import asyncio
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
import schedule


load_dotenv()
app = App(token=os.environ.get("SLACK_BOLT_TOKEN"))
slack_client = WebClient(token=os.environ.get("SLACK_WEB_CLI_TOKEN"))

# dict of tuples to store messages
# key: timestamp, value: (user, text)
message_memory = {}
username_dict = {}



####### Message logging #######

async def get_user_name(user_id):
    user_info = slack_client.users_info(user=user_id)
    return user_info["user"]["real_name"]

def log_original_message(channel, ts, user, text):
    # check if  channel exists in the dict
    if channel not in message_memory:
        message_memory[channel] = {}

    # store the og message sent in the specific channel
    if user in username_dict:
        user_name = username_dict[user]
    else:
        user_name = asyncio.run(get_user_name(user))
        username_dict[user] = user_name
    message_memory[channel][ts] = (user_name, text)

def handle_message_change(channel, event):
    ts, text = event["message"]["ts"], event["message"]["text"]
    user = event["message"]["user"]

    # replace the og message with the edited version
    user_name = username_dict[user]
    message_memory[channel][ts] = (user_name, text)

@app.event("message")
def log_message(event):
    if "subtype" in event and event["subtype"] == "message_changed":
        channel = event["channel"]
        handle_message_change(channel, event)
    else:
        user, text, ts, channel = event["user"], event["text"], event["ts"], event["channel"]
        log_original_message(channel, ts, user, text)



####### Writing Message to Disk #######

def write_messages_to_disk():
    # mkdir for each channel and save messages to a compressed file
    for channel_id, messages in message_memory.items():
        channel_info = slack_client.conversations_info(channel=channel_id)
        channel_name = channel_info["channel"]["name"]
        folder_path = f'/mnt/hd1/slack_archives/{channel_name}'
        os.makedirs(folder_path, exist_ok=True)

        file_path = f'{folder_path}/messages_{datetime.now().strftime("%Y-%m-%d")}.txt.gz'

        with gzip.open(file_path, 'wt') as file:
            for ts, (user_name, text) in messages.items():
                line = f"{user_name}:\t{text}\n"
                file.write(line)


def doing_something_idk():
    write_messages_to_disk()

    # flushing out the memory for next days' messages
    global message_memory
    global username_dict
    message_memory = {}
    username_dict = {}

schedule.every().day.at("11:59").do(doing_something_idk)

async def run_schedule_write():
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    # start the slack app in a separate thread
    slack_thread = threading.Thread(target=SocketModeHandler(app, os.environ["SLACK_BOLT_TOKEN"]).start)
    slack_thread.start()

    # run the scheduled task in the main thread
    asyncio.run(run_schedule_write())

