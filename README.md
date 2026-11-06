# Bluesky Language Dashboard

A live dashboard of the languages people post in on Bluesky. Every hour a scheduled GitHub Action samples a few minutes of public posts from Bluesky's Jetstream feed, runs language identification on each post and saves summary statistics to this repository.

The main question is how well the language a user declares matches the language they actually write in. Bluesky lets posters tag each post with a language, and those tags drive feeds and translation. This project compares the tags against an automatic detector and looks at where they disagree.

## What it measures

- Share of posts in each declared language, and how that shifts across the day
- Match rate between the declared tag and the detected language
- Which languages get confused with which (for example Ukrainian posts tagged as Russian)
- Mixed Cyrillic and Latin script, which can signal transliteration or code-switching
- Post length, type-token ratio, emoji use and link sharing per language
- How a language's tag accuracy changes over time

## How it works

`collector.py` connects to Jetstream, keeps newly created posts and stops after five minutes or 5,000 posts. `analysis.py` cleans each post (removing links, mentions, hashtags and emoji), detects its language with [lingua](https://github.com/pemistahl/lingua-py) and computes text features. The results are grouped by declared language and appended to two CSV files.

| File | One row per |
| --- | --- |
| `language_summary.csv` | language per sample |
| `language_pairs.csv` | declared and detected language pair per sample |

Only aggregate statistics are stored. No post text or account identifiers are saved.

## The dashboard

`dashboard.py` is a Dash app built on the two CSV files. It shows

- each language's share of posts over time
- how often each language tag matches the detected language
- a heatmap of declared tags against detected languages
- a focus view for one language, with where its posts end up and how its tag accuracy changes over time
- a sortable table of text statistics per language

Filters for the time window and languages sit above the charts. The app reloads the data every 15 minutes.

## Running it locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python test_offline.py
python collector.py --seconds 60
python dashboard.py
```

Then open http://127.0.0.1:8050 in a browser. To view the latest data from GitHub without pulling first, set `DATA_BASE_URL` to the raw file location before starting the app.

```bash
export DATA_BASE_URL=https://raw.githubusercontent.com/USERNAME/bluesky-language-dashboard/main/
python dashboard.py
```

`test_offline.py` checks the parsing and analysis code on sample posts without connecting to Bluesky.

## Known limitations

- Detection is unreliable on very short posts, so posts under 20 characters after cleaning are marked as undetermined (`und`).
- The detector only chooses among the 20 languages listed in `analysis.py`. A post in any other language may be assigned the closest listed language.
- Token counts split on spaces and punctuation, which undercounts words in Japanese and Chinese.
- Each sample covers a few minutes per hour, so the numbers estimate overall activity rather than counting every post.

## Data source

Posts come from Bluesky's public [Jetstream](https://github.com/bluesky-social/jetstream) service.
