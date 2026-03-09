![Alt text](https://files.catbox.moe/maih5a.png "a title")
# twitterweb-dl
This is a twitter scraper that makes use of the wonderful gallery-dl

https://github.com/mikf/gallery-dl


## Setup
1. Make sure you have your twitter cookies handy. I use the following extension to fetch them but please do your own research to ensure you trust it:
    - https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc

2. Download python 3.12 

    - If you don't have Python installed, download it from the [official Python website](https://www.python.org/downloads/).
    - Make sure to add it to your PATH

3. Clone this repo. You can download it by clicking Code > Download Zip
    - Extract it where you want your archiver to live
3. (OPTIONAL) Set up your venv
    - Ensure you are in the directory of the parse.pyw
```cmd
python -m venv venv
.\venv\Scripts\activate
```
 You should see (venv) in your terminal now.

5. Install requirements
```
pip install -r requirements.txt
```

## How to use
```
# downloads all tweets from a user
python parsev.py -u username -t

# can specify timeframe
# please set this if running for the first time to prevent rate limits
python parsev.pyw -u username -t --since 2020-08-25

# can fetch your own likes (starts from newest like)
python parsev.pyw-u your_username -l


#Run the help command for more information
py .\parsev.pyw --help
usage: parsev.pyw [-h] -u USERNAME [-c COOKIE] [-d DEST] [-t] [-l] [-s SINCE] [-e UNTIL]

Archive Twitter/X profiles and likes using gallery-dl.

options:
  -h, --help            show this help message and exit
  -u USERNAME, --username USERNAME
                        The Twitter username to archive
  -c COOKIE, --cookie COOKIE
                        Path to your x.com_cookies.txt file (default: current dir)
  -d DEST, --dest DEST  Destination path for gallery-dl (default: current dir)
  -t, --tweets          Download the user's tweets and retweets (Default if neither is specified)
  -l, --likes           Download the user's likes
  -s SINCE, --since SINCE
                        Start date in YYYY-MM-DD format (e.g., 2020-05-01)
  -e UNTIL, --until UNTIL
                        End date in YYYY-MM-DD format (e.g., 2023-12-31)
```

Within your selected director, tweets are archived in a subdirectory called twitter\username\ (both .json files with tweets and the media)

QRTs and retweets are also saved in their own folders.


## Additional Notes:
- Rate limits in the [advanced search](https://x.com/search?q=(from%3Aibxtoycat)%20until%3A2026-03-10%20since%3A2026-02-19&src=typed_query&f=live) are pretty strict. So if you get heavily rate-limited, might wanna come back the next day to try again.

## To Do:
- Ensure compatibility with linux and osx
- frontend