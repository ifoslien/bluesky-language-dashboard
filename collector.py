"""Sample live Bluesky posts from Jetstream and save language statistics.

Run it with
    python collector.py
or change the sample length with
    python collector.py --seconds 120 --max-posts 2000

Each run appends rows to three CSV files. Only aggregate statistics and
hashtags are saved, never post text or account IDs, so the data files
are safe to commit to a public repository.
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone

import pandas as pd
from websockets.sync.client import connect

from analysis import annotate_post, summarize

# Official public Jetstream instances run by Bluesky. The collector tries
# them in order and moves on if one is down.
JETSTREAM_HOSTS = [
    "jetstream2.us-east.bsky.network",
    "jetstream1.us-east.bsky.network",
    "jetstream1.us-west.bsky.network",
    "jetstream2.us-west.bsky.network",
]

SUMMARY_FILE = "language_summary.csv"
PAIRS_FILE = "language_pairs.csv"
HASHTAGS_FILE = "hashtags.csv"


def parse_event(message):
    """Pull the text and language tags out of one Jetstream message.

    Returns None for anything that is not a newly created post with text.
    """
    event = json.loads(message)
    if event.get("kind") != "commit":
        return None

    commit = event.get("commit", {})
    if commit.get("operation") != "create":
        return None
    if commit.get("collection") != "app.bsky.feed.post":
        return None

    record = commit.get("record", {})
    text = record.get("text", "").strip()
    if not text:
        return None

    return {"text": text, "langs": record.get("langs", [])}


def stream_posts(seconds, max_posts):
    """Collect raw posts from the first Jetstream host that answers."""
    for host in JETSTREAM_HOSTS:
        url = f"wss://{host}/subscribe?wantedCollections=app.bsky.feed.post"
        posts = []
        try:
            print(f"Connecting to {host}")
            with connect(url, max_size=2**20, open_timeout=15) as ws:
                end_time = time.time() + seconds
                while time.time() < end_time and len(posts) < max_posts:
                    try:
                        message = ws.recv(timeout=10)
                    except TimeoutError:
                        continue
                    post = parse_event(message)
                    if post:
                        posts.append(post)
            return posts
        except Exception as error:
            print(f"Could not use {host} because of {error}")
            if posts:
                return posts

    raise RuntimeError("No Jetstream host could be reached")


def append_rows(rows, filename):
    """Add rows to a CSV file, writing the header only for a new file."""
    if not rows:
        return
    df = pd.DataFrame(rows)
    write_header = not os.path.exists(filename)
    df.to_csv(filename, mode="a", header=write_header, index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=300)
    parser.add_argument("--max-posts", type=int, default=5000)
    args = parser.parse_args()

    run_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_posts = stream_posts(args.seconds, args.max_posts)
    print(f"\nCollected {len(raw_posts)} posts")

    start = time.time()
    annotated = [annotate_post(p["text"], p["langs"]) for p in raw_posts]
    print(f"Annotated in {time.time() - start:.1f} seconds")

    summary_rows, pair_rows, hashtag_rows = summarize(annotated, run_time)
    append_rows(summary_rows, SUMMARY_FILE)
    append_rows(pair_rows, PAIRS_FILE)
    append_rows(hashtag_rows, HASHTAGS_FILE)

    print("\nPosts by declared language")
    for row in sorted(summary_rows, key=lambda r: -r["posts"]):
        print(f"{row['declared']:>6}  {row['posts']:>5}  match rate {row['match_rate']}")


if __name__ == "__main__":
    main()
