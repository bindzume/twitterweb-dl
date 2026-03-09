import os
import json
import pandas as pd
from datetime import date, datetime, timedelta
import subprocess
import csv
from enum import Enum
import argparse

GLOBAL_CREATE_WINDOW=True

class CONFTYPE(Enum):
    LIKES = 1
    RETWEETS = 2
    TWEETS = 3

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
    else:
        raise ValueError("You passed the wrong conf type somewhere")
    
    return json_string.replace("{VAR_USERNAME}", username).replace("{VAR_BASE_DIRECTORY}", base_path.replace("\\", "\\\\"))

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
    
    command = f'gallery-dl.exe -A 10 -C "{cookie_path}" -c "{conf_file_path}" --dest "{gallery_dl_path}" "https://x.com/{username}/likes"'
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
    command = f'gallery-dl.exe -A 10 -C "{cookie_path}" -c "{conf_path}" --dest "{gallery_dl_path}" "https://twitter.com/search?q=(from%3A{username})%20until%3A{end_date}%20since%3A{oldest_date}&src=typed_query&f=live"'
    print(command)

    if(GLOBAL_CREATE_WINDOW):
        #since we are scraping the advanced search page, we have to scrape the retweets separately since they don't show up in the search results.
        subprocess.run(command)
        #for retweets
        command = f'gallery-dl.exe -A 11 -C "{cookie_path}" -c "{retweet_conf_file_path}" --dest "{gallery_dl_path}" "https://twitter.com/{username}"'
        subprocess.run(command)
    else:
        CREATE_NO_WINDOW = 0x08000000
        subprocess.run(command, creationflags=CREATE_NO_WINDOW)
        command = f'gallery-dl.exe -A 11 -C "{cookie_path}" -c "{retweet_conf_file_path}" --dest "{gallery_dl_path}" "https://twitter.com/{username}"'
        subprocess.run(command, creationflags=CREATE_NO_WINDOW)

   
    parse_folder(folder_path, output_csv)
    if(os.path.exists(os.path.join(folder_path, 'quote-retweets'))):
        parse_folder(os.path.join(folder_path, 'quote-retweets'), qrt_output_csv)
    if(os.path.exists(os.path.join(folder_path, 'retweets'))):
        print("found it")
        parse_folder(os.path.join(folder_path, 'retweets'), rt_output_csv)


def save_user(username, cookie_path, gallery_dl_path, since_date=None, until_date=None):
    conf_file_path = os.path.join(gallery_dl_path, "twitter", username, "gallery-dl-"+username+".conf")
    retweet_conf_file_path = os.path.join(gallery_dl_path, "twitter", username, "gallery-dl-"+username+"_retweet.conf")
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

    get_unfound_tweets(json_path, output_csv_path, gallery_dl_path, username, cookie_path, conf_file_path, retweet_conf_file_path, qrt_output_csv, rt_output_csv, since_date, until_date)

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

    # Date range arguments
    parser.add_argument("-s", "--since", help="Start date in YYYY-MM-DD format (e.g., 2020-05-01)")
    parser.add_argument("-e", "--until", help="End date in YYYY-MM-DD format (e.g., 2023-12-31)")

    args = parser.parse_args()

    if not args.tweets and not args.likes:
        args.tweets = True

    print(f"Archiving data for: {args.username}")
    
    if args.tweets:
        print("Starting tweets download...")
        # Pass the new date arguments into save_user
        save_user(args.username, args.cookie, args.dest, args.since, args.until)
        
    if args.likes:
        print("Starting likes download...")
        get_likes(args.username, args.cookie, args.dest)
