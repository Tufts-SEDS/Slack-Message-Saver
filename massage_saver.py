# activate the venv for the script using source ./slack_bot/bin/activate

import os
import re
import json
import gzip
import asyncio
import threading
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
import schedule
from pathlib import Path


load_dotenv()
app = App(token=os.environ.get("SLACK_BOLT_TOKEN"))
slack_client = WebClient(token=os.environ.get("SLACK_WEB_CLI_TOKEN"))

# dict of tuples to store messages
# key: timestamp, value: (user, text)
message_memory = {}
username_dict = {}
file_memory = {}



# Replace user IDs with usernames, used gpt for this but it works
def replace_user_ids_with_names(text):
    # Find all occurrences of '<@U...>'
    user_ids = re.findall(r'<@(U\w+)>', text)
    for user_id in user_ids:
        # Lookup user info by user ID
        user_info = slack_client.users_info(user=user_id)
        username = user_info['user']['name']
        # Replace '<@U...>' with '@username'
        text = text.replace(f'<@{user_id}>', f'@{username}')
    return text




####### Message logging #######

async def get_user_name(user_id):
    user_info = slack_client.users_info(user=user_id)
    return user_info["user"]["real_name"]

def log_original_message(channel, ts, user, text):
    # check if  channel exists in the dict
    if channel not in message_memory:
        message_memory[channel] = {}
        
    if "<@U" in text:
        text = replace_user_ids_with_names(text)

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


@app.event("file_shared")
def log_file_shared(event):
    if event["type"] == "file_shared":
        file_info = slack_client.files_info(file=event["file_id"])
        print(file_info)



####### File handling #######

@app.event("file_shared")
def log_file_shared(event):
    if event["type"] == "file_shared":
        file_info = slack_client.files_info(file=event["file_id"])
        filename = file_info["file"]["name"]
        file_url = file_info["file"]["url_private_download"]
        file_extension = file_info["file"]["filetype"]
        if filename in file_memory:
            pass
        else:
            file_memory[event["channel"]][event["event_ts"]] = (filename, file_url, file_extension)

def download_file(url, filename, headers):
    try:
        with requests.get(url, headers=headers, stream=True) as req:
            with gzip.open(file_path, 'wt') as f:
                for chunk in req.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
        return filename
    except Exception as e:
        print(e)
        return None

def add_file_extension(filename, extension):
    # Check if the filename already has an extension
    if not "." in filename:
        # Append the extension if it doesn't have one
        filename += "." + extension
    return filename



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
                # convert Unix timestamp to datetime object
                dt_object = datetime.fromtimestamp(float(ts))

                # convert datetime object to a string with the desired time format
                formatted_time = dt_object.strftime("%H:%M:%S")
                line = f"{formatted_time} - {user_name}:\t{text}\n"
                file.write(line)
                
def write_files_to_disk():
    # mkdir for each channel and save messages to a compressed file
    for channel_id, sharedfiles in file_memory.items():
        channel_info = slack_client.conversations_info(channel=channel_id)
        channel_name = channel_info["channel"]["name"]
        folder_path = f'/mnt/hd1/slack_archives/{channel_name}/media'
        os.makedirs(folder_path, exist_ok=True)

        
        for ts, (filename, file_url, extension) in sharedfiles.items():
            fixed_filename = add_file_extension(filename, extension)
            file_path = f'{folder_path}/{datetime.now().strftime("%Y-%m-%d")}/{fixed_filename}.gz'
            
            # adding a token as a header so we get permission to download the file
            token = os.environ.get("SLACK_WEB_CLI_TOKEN")
            tokenSlackAuth = f"Bearer {token}"
            headers = {"Authorization": tokenSlackAuth, "content-type": "application/json"}
            download_file(file_url, file_path, headers)
            

def doing_something_idk():
    write_messages_to_disk()
    write_files_to_disk()

    # flushing out the memory for next days' messages
    global message_memory
    global username_dict
    global file_memory
    message_memory = {}
    username_dict = {}
    file_memory = {}

schedule.every().day.at("23:59").do(doing_something_idk)

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
