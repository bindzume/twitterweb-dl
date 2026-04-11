import os
import json
import pandas as pd
from datetime import date, datetime, timedelta
import subprocess
from enum import Enum
import argparse
import urllib.request # <--- Add this line
import sys
import threading
from queue import Queue, Empty
GLOBAL_CREATE_WINDOW=True

dash_a = 4

class DualLogger:
    def __init__(self, filepath):
        self.terminal = sys.stdout
        self.log_file = open(filepath, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()



class CONFTYPE(Enum):
    LIKES = 1
    RETWEETS = 2
    TWEETS = 3
    REPLIES = 4
    TIMELINE = 5 # <--- Added this

def parse_json_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
        return {
            'id': '\'' + str(data.get('tweet_id', '')),
            'conversation_id': '\'' + str(data.get('conversation_id', '')),
            'date': data.get('date', ''),
            'content': data.get('content', ''),
            'author': data.get('author')["name"],
            'media_type': 'media' if data.get('count') > 0 else 'text',
            'tweet_type': 'main' if data.get('reply_id') == 0 else 'reply',
            'link': 'twitter.com/user/status/' + str(data.get('tweet_id', '')),
            'likes': data.get('favorite_count'),
            'replies': data.get('reply_count'),
            'retweets': data.get('retweet_count'),
            'quote_retweets':data.get('quote_count'),
            'quote_id': '\'' + str(data.get('quote_id', ''))
            }
    
def run_command_emergency(command, creationflags=0, max_strikes=2, inactivity_timeout=15):
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, 
        text=True,
        bufsize=1, 
        creationflags=creationflags
    )

    def read_output(pipe, q):
        for line in pipe:
            q.put(line)
        pipe.close()

    output_queue = Queue()
    reader_thread = threading.Thread(target=read_output, args=(process.stdout, output_queue))
    reader_thread.daemon = True 
    reader_thread.start()

    # --- BRAIN 2: The Watchdog ---
    rate_limit_strikes = 0
    current_timeout = inactivity_timeout 

    while True:
        if process.poll() is not None and output_queue.empty():
            break

        try:
            # timeout=None means it will wait forever. timeout=15 means it watches for freezes.
            line = output_queue.get(timeout=current_timeout)
            
            sys.stdout.write(line)
            sys.stdout.flush()

            # --- Check Condition 1: Rate Limit Strikes ---
            if "Waiting until" in line and "(rate limit)" in line:
                rate_limit_strikes += 1
                
                if rate_limit_strikes >= max_strikes:
                    print(f"\n\n[!] Detected {max_strikes} rate limit warnings in a row!")
                    print("[!] gallery-dl is trapped. Force-killing the process...")
                    process.terminate()
                    break
                else:
                    # SUCCESS: Suspend the watchdog.
                    print("\n[*] Rate limit pause detected. Disabling the freeze watchdog until it wakes up...")
                    current_timeout = None # <--- Turns off the inactivity timer!
            else:
                # Normal download text! Reset strikes and re-enable the 15-second watchdog
                rate_limit_strikes = 0
                current_timeout = inactivity_timeout

        except Empty:
            # --- Check Condition 2: Inactivity Timeout ---
            # This will ONLY trigger if current_timeout was a number (like 15) and time ran out
            print(f"\n\n[!] gallery-dl has been frozen for {inactivity_timeout} seconds without output!")
            print("[!] Force-killing the process and moving to the next step...")
            process.terminate()
            break

    process.wait()

def parse_folder(folder_path, output_csv):
    data_list = []
    data_dict = dict()
    print('done')
    
    if os.path.exists(output_csv):
        existing_df = pd.read_csv(output_csv)
        data_list.extend(existing_df.to_dict('records'))
        
        
    for filename in os.listdir(folder_path):
        if filename.endswith('json'):
            file_path = os.path.join(folder_path, filename)
            parsed_data = parse_json_file(file_path)
            data_list.append(parsed_data)

    print('done1')
    data_list.reverse()
    dupe_tweets = []
    found_tweets = []
    new_data_list = []
    #print(data_list[0]['id'])
    for d in data_list:
        if(d['id'] in found_tweets):
            dupe_tweets.append(d['id'])
        else:
            found_tweets.append(d['id'])
            new_data_list.append(d)
    
    print('done2')
    #data_list = [dict(t) for t in {tuple(d.items()) for d in data_list}]    
    df = pd.DataFrame(new_data_list)
    df.to_csv(output_csv, index=False)

def get_recent_timeline(folder_path, output_csv, qrt_output_csv, rt_output_csv, username, cookie_path, standard_conf_path, timeline_conf_path):
    # 1. Grab normal timeline (Tweets + Retweets)
    print(f"Syncing recent timeline (Tweets & RTs) for {username}...")
    url_timeline = f"https://x.com/{username}/with_replies"
    command_timeline = f'gallery-dl.exe -A {dash_a} -C "{cookie_path}" -c "{timeline_conf_path}" "{url_timeline}"'
    
    if GLOBAL_CREATE_WINDOW:
        run_command_emergency(command_timeline)
    else:
        CREATE_NO_WINDOW = 0x08000000
        run_command_emergency(command_timeline, creationflags=CREATE_NO_WINDOW)

    # 2. Grab with_replies timeline (Replies)
    #print(f"Syncing recent replies for {username}...")
    #url_replies = f"https://x.com/{username}/with_replies"
    #command_replies = f'gallery-dl.exe -A {dash_a} -C "{cookie_path}" -c "{timeline_conf_path}" "{url_replies}"'
    
    #if GLOBAL_CREATE_WINDOW:
    #    run_command_emergency(command_replies)
    #else:
    #    CREATE_NO_WINDOW = 0x08000000
    #    run_command_emergency(command_replies, creationflags=CREATE_NO_WINDOW)

    # 3. Parse everything identically to get_unfound_tweets
    print(f"Parsing downloaded files into CSVs for {username}...")
    parse_folder(folder_path, output_csv)
    
    if os.path.exists(os.path.join(folder_path, 'quote-retweets')):
        parse_folder(os.path.join(folder_path, 'quote-retweets'), qrt_output_csv)
        
    if os.path.exists(os.path.join(folder_path, 'retweets')):
        print("found it")
        parse_folder(os.path.join(folder_path, 'retweets'), rt_output_csv)

def get_conf_template(conf_type, username, base_path):
    json_string = ''
    if(conf_type == CONFTYPE.LIKES):
        with open('conf-template-likes.json') as f:
            json_string = f.read()
            
    elif(conf_type == CONFTYPE.RETWEETS):
        with open('conf-template-retweets.json') as f:
            json_string = f.read()
    elif(conf_type == CONFTYPE.TWEETS):
        with open('conf-template-tweets.json') as f:
            json_string = f.read()
    elif(conf_type == CONFTYPE.REPLIES): # <--- Added this block
        with open('conf-template-replies.json') as f:
            json_string = f.read()
    elif(conf_type == CONFTYPE.TIMELINE): # <--- Added this block
        with open('conf-template-timeline.json') as f:
            json_string = f.read()
    else:
        raise ValueError("You passed the wrong conf type somewhere")
    
    return json_string.replace("{VAR_USERNAME}", username).replace("{VAR_BASE_DIRECTORY}", base_path.replace("\\", "\\\\"))


def get_replied_to_tweets(folder_path, username, cookie_path, replies_conf_path):
    reply_ids = set()
    
    # 1. Scan the main folder for JSONs and grab the reply_ids
    for filename in os.listdir(folder_path):
        if filename.endswith('.json'):
            file_path = os.path.join(folder_path, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    reply_id = data.get('reply_id', 0)
                    if reply_id != 0:
                        # Store as string for easy comparison
                        reply_ids.add(str(reply_id)) 
            except Exception as e:
                print(f"Error parsing {filename}: {e}")

    if not reply_ids:
        print("No replies found to download.")
        return

    # 2. Check the existing replies CSV to filter out what we already have
    replies_csv = os.path.join(folder_path, "replies_output.csv")
    existing_reply_ids = set()
    
    if os.path.exists(replies_csv):
        try:
            df_existing = pd.read_csv(replies_csv)
            # The IDs in the CSV start with a single quote (e.g., "'12345"). 
            # We strip the quote out so it matches our raw JSON reply_ids.
            existing_reply_ids = set(df_existing['id'].astype(str).str.replace("'", ""))
        except Exception as e:
            print(f"Error reading {replies_csv}: {e}")

    # Subtract the already downloaded IDs from the total IDs we found
    new_reply_ids = reply_ids - existing_reply_ids

    if not new_reply_ids:
        print("All replied-to tweets have already been downloaded! Skipping gallery-dl.")
        return

    # 3. Save only the NEW IDs as URLs to a text file for gallery-dl to read
    urls_file = os.path.join(folder_path, "replies_to_fetch.txt")
    with open(urls_file, "w") as f:
        for rid in new_reply_ids:
            f.write(f"https://x.com/i/status/{rid}\n")

    # 4. Call gallery-dl using the -i (input file) command
    command = f'gallery-dl.exe -A {dash_a} -C "{cookie_path}" -c "{replies_conf_path}" -i "{urls_file}"'
    print(f"Downloading {len(new_reply_ids)} new replied-to tweets into the replies folder...")
    
    if GLOBAL_CREATE_WINDOW:
        subprocess.run(command)
    else:
        CREATE_NO_WINDOW = 0x08000000
        subprocess.run(command, creationflags=CREATE_NO_WINDOW)
        
    # 5. Parse the replies folder into a CSV
    replies_dir = os.path.join(folder_path, "replies")
    if os.path.exists(replies_dir):
        parse_folder(replies_dir, replies_csv)

# gets your twitter likes. only works for your own account obviously
def get_likes(username, cookie_path, gallery_dl_path):
    
    conf_file_path = os.path.join(gallery_dl_path, "twitter", username, "gallery-dl-"+username+".conf")
    folder_path= os.path.join(gallery_dl_path, "twitter", username)
    output_csv= os.path.join(gallery_dl_path, "twitter", username, "output.csv")
    conf_file_path = os.path.join(gallery_dl_path, "twitter", username, "gallery-dl-"+ username +".conf")

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    if(not os.path.exists(conf_file_path)):
        conf_template = get_conf_template(CONFTYPE.LIKES, username, gallery_dl_path)
        with open(conf_file_path, 'w') as f:
            f.write(conf_template)
    
    command = f'gallery-dl.exe -A {dash_a} -C "{cookie_path}" -c "{conf_file_path}" --dest "{gallery_dl_path}" "https://x.com/{username}/likes"'
    print(command)
    subprocess.run(command)

    parse_folder(folder_path, output_csv)

#Makes a folder for your user in your "gallery_dl_path"
# In that folder, all tweet .jsons and all media is stored
# In that folder, rt_output.csv, qrt_output.csv, and output.csv are generated
# In the retweets folder, all tweets that the user retweeted and their associated media is stored
# In the quote-retweets folder, all tweets that the user quote-tweeted are stored (not what they said. that is in regular tweets folder).
# In the qrt_output.csv, there is a quote_id that links to the user you are archiving's tweet. 
def get_unfound_tweets(folder_path, output_csv, gallery_dl_path, username, cookie_path, conf_path, retweet_conf_file_path, qrt_output_csv, rt_output_csv, since_date=None, until_date=None):
    
    # Use the provided since_date, OR default to 2006 if they didn't provide one
    oldest_date = since_date if since_date else '2006-03-21'

    # If an output CSV exists, and they DIDN'T provide a custom --since date, 
    # find the most recent tweet we have so we don't redownload old ones.
    if os.path.exists(output_csv) and not since_date:
        tweet_list = pd.read_csv(output_csv).to_dict('records')
        for tweet in tweet_list:
            if(tweet['date'] > oldest_date):
                oldest_date = tweet['date']
        
        # Only subtract 2 days if we pulled the date from the CSV (to ensure overlap)
        oldest_date = oldest_date.split()[0]
        oldest_date = (datetime.strptime(oldest_date, "%Y-%m-%d") - timedelta(days=2)).strftime("%Y-%m-%d")

    # Set the end date (custom --until date, or default to 2 days in the future)
    end_date = until_date if until_date else (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")

    # The updated command using oldest_date and end_date
    command = f'gallery-dl.exe -A {dash_a} -C "{cookie_path}" -c "{conf_path}" --dest "{gallery_dl_path}" "https://twitter.com/search?q=(from%3A{username})%20until%3A{end_date}%20since%3A{oldest_date}&src=typed_query&f=live"'
    print(command)

    if(GLOBAL_CREATE_WINDOW):
        #since we are scraping the advanced search page, we have to scrape the retweets separately since they don't show up in the search results.
        subprocess.run(command)
        #for retweets
        command = f'gallery-dl.exe -A {dash_a} -C "{cookie_path}" -c "{retweet_conf_file_path}" --dest "{gallery_dl_path}" "https://twitter.com/{username}"'
        subprocess.run(command)
    else:
        CREATE_NO_WINDOW = 0x08000000
        subprocess.run(command, creationflags=CREATE_NO_WINDOW)
        command = f'gallery-dl.exe -A {dash_a} -C "{cookie_path}" -c "{retweet_conf_file_path}" --dest "{gallery_dl_path}" "https://twitter.com/{username}"'
        subprocess.run(command, creationflags=CREATE_NO_WINDOW)

   
    parse_folder(folder_path, output_csv)
    if(os.path.exists(os.path.join(folder_path, 'quote-retweets'))):
        parse_folder(os.path.join(folder_path, 'quote-retweets'), qrt_output_csv)
    if(os.path.exists(os.path.join(folder_path, 'retweets'))):
        print("found it")
        parse_folder(os.path.join(folder_path, 'retweets'), rt_output_csv)

def update_profile_info(folder_path, username):
    print(f"Checking for profile updates for {username}...")
    
    # 1. Find the most recently modified .json file in the folder
    json_files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
    if not json_files:
        return # No JSONs downloaded yet
        
    latest_json = max(json_files, key=lambda x: os.path.getmtime(os.path.join(folder_path, x)))
    
    avatar_url = None
    banner_url = None
    
    try:
        with open(os.path.join(folder_path, latest_json), 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Prioritize 'user' (the timeline owner) over 'author'
            user_data = data.get('user', data.get('author', {}))
            avatar_url = user_data.get('profile_image')
            banner_url = user_data.get('profile_banner')
    except Exception as e:
        print(f"Error reading JSON for profile info: {e}")
        return

    profile_dir = os.path.join(folder_path, "profile-info")
    os.makedirs(profile_dir, exist_ok=True)
    
    # Helper function to download images with a fake Browser User-Agent
    def download_image(url, save_path):
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0'}
        )
        with urllib.request.urlopen(req) as response, open(save_path, 'wb') as out_file:
            out_file.write(response.read())

    # 4. Check and Download Avatar
    if avatar_url:
        avatar_id = avatar_url.split('/')[-1]
        avatar_filename = f"avatar_{avatar_id}"
        avatar_path = os.path.join(profile_dir, avatar_filename)
        
        if not os.path.exists(avatar_path):
            print(f"New profile picture detected! Saving {avatar_filename}...")
            try:
                download_image(avatar_url, avatar_path)
            except Exception as e:
                print(f"Failed to download avatar: {e}")
                
    # 5. Check and Download Banner
    if banner_url:
        banner_id = banner_url.split('/')[-1]
        banner_filename = f"banner_{banner_id}.jpg"
        banner_path = os.path.join(profile_dir, banner_filename)
        
        if not os.path.exists(banner_path):
            print(f"New profile banner detected! Saving {banner_filename}...")
            try:
                # Twitter banners usually need the size appended
                download_image(banner_url + "/1500x500", banner_path)
            except Exception as e:
                try:
                    # Fallback to the base URL
                    download_image(banner_url, banner_path)
                except Exception as fallback_e:
                    print(f"Failed to download banner: {fallback_e}")

def save_user(username, cookie_path, gallery_dl_path, since_date=None, until_date=None, fetch_replies=False):
    conf_file_path = os.path.join(gallery_dl_path, "twitter", username, "gallery-dl-"+username+".conf")
    retweet_conf_file_path = os.path.join(gallery_dl_path, "twitter", username, "gallery-dl-"+username+"_retweet.conf")
    replies_conf_file_path = os.path.join(gallery_dl_path, "twitter", username, "gallery-dl-"+username+"_replies.conf") # <--- Added
    timeline_conf_file_path = os.path.join(gallery_dl_path, "twitter", username, "gallery-dl-"+username+"_timeline.conf") # <--- Added

    json_path= os.path.join(gallery_dl_path, "twitter", username)
    output_csv_path= os.path.join(gallery_dl_path, "twitter", username, "output.csv")
    qrt_output_csv = os.path.join(gallery_dl_path, "twitter", username, "qrt_output.csv")
    rt_output_csv = os.path.join(gallery_dl_path, "twitter", username, "rt_output.csv")

    if(not os.path.exists(json_path)):
        os.makedirs(json_path)
        
    if(not os.path.exists(conf_file_path)):
        conf_template = get_conf_template(CONFTYPE.TWEETS, username, gallery_dl_path)
        with open(conf_file_path, 'w') as f:
            f.write(conf_template)

    if(not os.path.exists(retweet_conf_file_path)):
        retweet_conf_template = get_conf_template(CONFTYPE.RETWEETS, username, gallery_dl_path)
        with open(retweet_conf_file_path, 'w') as f:
            f.write(retweet_conf_template)

    # <--- Added Replies Config Generation
    if(not os.path.exists(replies_conf_file_path)):
        replies_conf_template = get_conf_template(CONFTYPE.REPLIES, username, gallery_dl_path)
        with open(replies_conf_file_path, 'w') as f:
            f.write(replies_conf_template)


    # <--- Generate Timeline config
    if(not os.path.exists(timeline_conf_file_path)):
        timeline_conf_template = get_conf_template(CONFTYPE.TIMELINE, username, gallery_dl_path)
        with open(timeline_conf_file_path, 'w') as f:
            f.write(timeline_conf_template)

    
    """ if(not os.path.exists(output_csv_path)):
        data = ["a"]
        with open(output_csv_path, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(data)

    if(not os.path.exists(qrt_output_csv)):
        data = ["a"]
        with open(qrt_output_csv, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(data)

    if(not os.path.exists(rt_output_csv)):
        data = ["a"]
        with open(rt_output_csv, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(data)
     """

# <--- The Hybrid Branch
    if since_date or until_date:
        print(f"Dates provided. Running Deep Archive via Search API...")
        get_unfound_tweets(json_path, output_csv_path, gallery_dl_path, username, cookie_path, conf_file_path, retweet_conf_file_path, qrt_output_csv, rt_output_csv, since_date, until_date)
    else:
        print(f"No dates provided. Running Fast Sync via Timeline...")
        # Passing folder_path (json_path), output_csv, qrt_output_csv, and rt_output_csv
        get_recent_timeline(json_path, output_csv_path, qrt_output_csv, rt_output_csv, username, cookie_path, conf_file_path, timeline_conf_file_path)

    # <--- Added fetch replies trigger
    if fetch_replies:
        print("Fetching replied-to tweets...")
        get_replied_to_tweets(json_path, username, cookie_path, replies_conf_file_path)

    update_profile_info(json_path, username)

if __name__ == "__main__":
    # Set up the argument parser
    parser = argparse.ArgumentParser(description="Archive Twitter/X profiles and likes using gallery-dl.")
    
    # Required username
    parser.add_argument("-u", "--username", required=True, help="The Twitter username to archive")
    
    # Optional paths with defaults
    parser.add_argument("-c", "--cookie", default="x.com_cookies.txt", help="Path to your x.com_cookies.txt file (default: current dir)")
    parser.add_argument("-d", "--dest", default=".", help="Destination path for gallery-dl (default: current dir)")

    # The Boolean flags for Tweets and Likes
    parser.add_argument("-t", "--tweets", action="store_true", help="Download the user's tweets and retweets (Default if neither is specified)")
    parser.add_argument("-l", "--likes", action="store_true", help="Download the user's likes")

    # <--- Add this argument so the user can toggle it
    parser.add_argument("-r", "--replies", action="store_true", help="Also download the original tweets the user replied to")

    # Date range arguments
    parser.add_argument("-s", "--since", help="Start date in YYYY-MM-DD format (e.g., 2020-05-01)")
    parser.add_argument("-e", "--until", help="End date in YYYY-MM-DD format (e.g., 2023-12-31)")

    args = parser.parse_args()

    if not args.tweets and not args.likes:
        args.tweets = True

    # --- LOGGING SETUP ---
    # 1. Create the 'logs' folder if it doesn't exist yet
    os.makedirs(os.path.join(args.dest, "twitter", args.username, "logs"), exist_ok=True)

    # 2. Generate an iterating filename using a timestamp (e.g., log_20231024_153022.txt)
    # Timestamps are better than counting (log_1, log_2) because they never collide!
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(args.dest, "twitter", args.username, "logs", f"run_{timestamp}.log")

    # 3. Hijack Python's output to use our DualLogger
    sys.stdout = DualLogger(log_filename)
    sys.stderr = sys.stdout # Routes any core Python crash errors into the log too!

    print(f"[*] Logging initialized. Saving copy of output to: {log_filename}")
    print("-" * 50)
    print(f"Archiving data for: {args.username}")
    
    if args.tweets:
        print("Starting tweets download...")
        # Pass the new date arguments into save_user
        save_user(args.username, args.cookie, args.dest, args.since, args.until, args.replies)
        
    if args.likes:
        print("Starting likes download...")
        get_likes(args.username, args.cookie, args.dest)
