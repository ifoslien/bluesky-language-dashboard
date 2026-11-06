"""Shared text analysis for the Bluesky language dashboard.

The collector imports these functions to annotate each post and then
summarize a sample. The dashboard will import them later too.
"""

import html
import re
from collections import Counter

from lingua import Language, LanguageDetectorBuilder

# Languages the detector can choose from. Limiting the list keeps detection
# fast and avoids rare-language false positives on short posts.
# Add or remove languages here to change what the dashboard tracks.
LANGUAGES = [
    Language.ENGLISH,
    Language.JAPANESE,
    Language.PORTUGUESE,
    Language.GERMAN,
    Language.SPANISH,
    Language.FRENCH,
    Language.KOREAN,
    Language.RUSSIAN,
    Language.UKRAINIAN,
    Language.ITALIAN,
    Language.DUTCH,
    Language.POLISH,
    Language.TURKISH,
    Language.SWEDISH,
    Language.FINNISH,
    Language.CATALAN,
    Language.INDONESIAN,
    Language.CHINESE,
    Language.ARABIC,
    Language.PERSIAN,
]

# Posts shorter than this after cleaning are too short to detect reliably
MIN_CHARS = 20

# Minimum detector confidence to accept a detected language
MIN_CONFIDENCE = 0.5

URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")
MENTION_PATTERN = re.compile(r"@[\w.\-]+")
HASHTAG_PATTERN = re.compile(r"#\w+")

EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]"
)
WORD_PATTERN = re.compile(r"\w+", re.UNICODE)
CYRILLIC_PATTERN = re.compile(r"[Ѐ-ӿ]")
LATIN_PATTERN = re.compile(r"[A-Za-z]")

_detector = None


def get_detector():
    """Build the lingua detector once and reuse it."""
    global _detector
    if _detector is None:
        _detector = (
            LanguageDetectorBuilder.from_languages(*LANGUAGES)
            .with_preloaded_language_models()
            .build()
        )
    return _detector


def clean_text(text):
    """Remove URLs, mentions, hashtags and emoji so only running text is left."""
    text = URL_PATTERN.sub(" ", text)
    text = MENTION_PATTERN.sub(" ", text)
    text = HASHTAG_PATTERN.sub(" ", text)
    text = EMOJI_PATTERN.sub(" ", text)
    return " ".join(text.split())


def detect_language(text):
    """Return an ISO 639-1 code and a confidence score, or 'und' if unsure."""
    cleaned = clean_text(text)
    if len(cleaned) < MIN_CHARS:
        return "und", 0.0

    values = get_detector().compute_language_confidence_values(cleaned)
    if not values:
        return "und", 0.0

    top = values[0]
    if top.value < MIN_CONFIDENCE:
        return "und", round(top.value, 3)
    return top.language.iso_code_639_1.name.lower(), round(top.value, 3)


def normalize_tag(tag):
    """Turn a declared tag like 'en-US' or 'pt-BR' into a base code like 'en'."""
    return tag.split("-")[0].lower()


def script_mix(text):
    """Label a post by the alphabets it uses, which helps spot transliteration."""
    has_cyrillic = bool(CYRILLIC_PATTERN.search(text))
    has_latin = bool(LATIN_PATTERN.search(clean_text(text)))
    if has_cyrillic and has_latin:
        return "mixed"
    if has_cyrillic:
        return "cyrillic"
    if has_latin:
        return "latin"
    return "other"


def annotate_post(text, langs):
    """Return a dictionary of features for one post."""
    text = html.unescape(text)
    declared_tags = [normalize_tag(t) for t in (langs or [])]
    declared = declared_tags[0] if declared_tags else "none"
    detected, confidence = detect_language(text)
    tokens = WORD_PATTERN.findall(clean_text(text).lower())

    return {
        "declared": declared,
        "multi_tag": len(declared_tags) > 1,
        "detected": detected,
        "confidence": confidence,
        "match": detected == declared,
        "chars": len(text),
        "tokens": tokens,
        "emoji": len(EMOJI_PATTERN.findall(text)),
        "has_url": bool(URL_PATTERN.search(text)),
        "script": script_mix(text),
    }


def summarize(posts, run_time, min_posts=20):
    """Collapse annotated posts into per-language summary rows.

    Returns two lists of dictionaries that become rows in
    language_summary.csv and language_pairs.csv.
    Languages with fewer than min_posts posts are grouped as 'other'
    so the summary only keeps languages with enough data to compare.
    """
    declared_counts = Counter(p["declared"] for p in posts)
    keep = {lang for lang, n in declared_counts.items() if n >= min_posts}

    groups = {}
    for p in posts:
        lang = p["declared"] if p["declared"] in keep else "other"
        groups.setdefault(lang, []).append(p)

    summary_rows = []
    for lang, group in sorted(groups.items()):
        all_tokens = [t for p in group for t in p["tokens"]]
        detectable = [p for p in group if p["detected"] != "und"]
        summary_rows.append({
            "run_time": run_time,
            "declared": lang,
            "posts": len(group),
            "share": round(len(group) / len(posts), 4),
            "detectable": len(detectable),
            "match_rate": round(
                sum(p["match"] for p in detectable) / len(detectable), 4
            ) if detectable else None,
            "multi_tag_rate": round(sum(p["multi_tag"] for p in group) / len(group), 4),
            "mean_chars": round(sum(p["chars"] for p in group) / len(group), 1),
            "mean_tokens": round(len(all_tokens) / len(group), 1),
            "type_token_ratio": round(len(set(all_tokens)) / len(all_tokens), 4)
            if all_tokens else None,
            "emoji_per_post": round(sum(p["emoji"] for p in group) / len(group), 3),
            "url_rate": round(sum(p["has_url"] for p in group) / len(group), 4),
            "mixed_script_rate": round(
                sum(p["script"] == "mixed" for p in group) / len(group), 4
            ),
        })

    pair_counts = Counter((p["declared"], p["detected"]) for p in posts)
    pair_rows = [
        {"run_time": run_time, "declared": d, "detected": t, "count": n}
        for (d, t), n in sorted(pair_counts.items())
    ]

    return summary_rows, pair_rows
