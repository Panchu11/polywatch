import json
import sys

# Load posted.json to get the trade IDs
with open('posted.json', encoding='utf-8') as f:
    posted_data = json.load(f)

print(f"Total trades posted: {len(posted_data['items'])}\n")

# Now run the bot 5 times and capture the tweets
import subprocess
import os

os.environ['DRY_RUN'] = 'true'
os.environ['GLOBAL_MODE'] = 'true'
os.environ['SINCE_MINUTES'] = '90'
os.environ['MIN_PROFIT_USD'] = '10000'
os.environ['MIN_TRADE_CASH'] = '100'
os.environ['FIREWORKS_API_KEY'] = 'fw_3ZTSMqy7FxU8zkrfr2DJWpVG'

for run in range(1, 6):
    print(f"\n{'='*80}")
    print(f"TEST RUN {run}")
    print(f"{'='*80}")
    result = subprocess.run(['python', 'polywatch.py'], capture_output=True, text=True)
    
    # Extract the trade ID from output
    for line in result.stdout.split('\n'):
        if 'DRY_RUN: would tweet' in line:
            print(line)
        if 'Posted 1 tweet' in line:
            print(line)

