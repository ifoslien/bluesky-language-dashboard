"""Check the parsing and analysis code without connecting to Bluesky.

Run it with
    python test_offline.py
"""

import json

from analysis import annotate_post, summarize
from collector import parse_event


def fake_message(text, langs, operation="create", collection="app.bsky.feed.post"):
    """Build a message shaped like a real Jetstream commit event."""
    return json.dumps({
        "did": "did:plc:example",
        "time_us": 1762400000000000,
        "kind": "commit",
        "commit": {
            "rev": "abc",
            "operation": operation,
            "collection": collection,
            "rkey": "xyz",
            "record": {
                "$type": "app.bsky.feed.post",
                "createdAt": "2026-11-05T12:00:00Z",
                "langs": langs,
                "text": text,
            },
        },
    })


samples = [
    ("Just finished reading a great book about the history of linguistics", ["en"]),
    ("Сегодня очень холодно, но я всё равно пойду гулять в парк", ["ru"]),
    ("Сьогодні дуже холодно, але я все одно піду гуляти до парку", ["ru"]),
    ("Hoje está muito frio, mas mesmo assim vou passear no parque", ["pt"]),
    ("Heute ist es sehr kalt, aber ich gehe trotzdem in den Park", ["en"]),
    ("今日はとても寒いですが、それでも公園に散歩に行きます", ["ja"]),
    ("lol same", ["en"]),
    ("Segodnya ochen kholodno, no ya vsyo ravno poydu gulyat", ["ru"]),
    ("Check this out https://example.com #linguistics #nlp 🎉🎉", ["en-US"]),
    ("Working on my thesis tonight, wish me luck with the data", []),
]

messages = [fake_message(t, l) for t, l in samples]
messages.append(fake_message("a like, not a post", ["en"], collection="app.bsky.feed.like"))
messages.append(fake_message("deleted post", ["en"], operation="delete"))
messages.append(json.dumps({"kind": "identity", "did": "did:plc:example"}))

parsed = [p for p in (parse_event(m) for m in messages) if p]
assert len(parsed) == len(samples), "non-post events should be skipped"
print(f"Parsed {len(parsed)} of {len(messages)} messages\n")

annotated = [annotate_post(p["text"], p["langs"]) for p in parsed]
for (text, _), a in zip(samples, annotated):
    print(f"declared {a['declared']:>4}  detected {a['detected']:>4}  "
          f"script {a['script']:>8}  {text[:45]}")

summary, pairs, hashtags = summarize(annotated, "2026-11-05T12:00:00Z", min_posts=1)

print("\nSummary rows")
for row in summary:
    print(row)

print("\nDeclared vs detected pairs")
for row in pairs:
    print(row)

print("\nHashtags")
for row in hashtags:
    print(row)
