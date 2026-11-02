import calendar
import html
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from itertools import zip_longest

import feedparser
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.summarizer import enrich

socket.setdefaulttimeout(10)  # a dead feed can't hang the server

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# Several sources per topic. Test each URL and swap out any that fail.
FEEDS = {
    "sports": [
        "https://feeds.bbci.co.uk/sport/rss.xml",
        "https://www.espn.com/espn/rss/news",
    ],
    "ai": [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    ],
    "finance": [
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "https://www.moneycontrol.com/rss/latestnews.xml",
    ],
}

# Clean display names for sources
SOURCE_NAMES = {
    "espn.com": "ESPN",
    "bbci.co.uk": "BBC Sport",
    "techcrunch.com": "TechCrunch",
    "theverge.com": "The Verge",
    "economictimes": "Economic Times",
    "moneycontrol.com": "Moneycontrol",
}

# Stories with these words in the title get dropped (event promos, fluff)
BLOCKLIST = ["summit", "halloween", "register", "tickets", "sponsor", "webinar"]

CACHE_TTL = 600  # seconds
_cache: dict = {}  # topic -> (fetched_at, stories)


def clean(text: str) -> str:
    text = re.sub(r"<[^>]*>", "", text or "")
    return html.unescape(text).strip()


def source_name(url: str, fallback: str) -> str:
    for key, name in SOURCE_NAMES.items():
        if key in url:
            return name
    return fallback


def parse_feed(args):
    topic, url = args
    try:
        parsed = feedparser.parse(url)
    except Exception:
        return []
    source = clean(parsed.feed.get("title", "Unknown")).split("|")[0].strip()
    source = source_name(url, source)
    stories = []
    for e in parsed.entries[:20]:
        title = clean(e.get("title", ""))
        if not title or any(w in title.lower() for w in BLOCKLIST):
            continue
        ts = 0
        if e.get("published_parsed"):
            ts = calendar.timegm(e.published_parsed)
        stories.append({
            "title": title,
            "link": e.get("link", ""),
            "summary": clean(e.get("summary", ""))[:300],
            "published": e.get("published", ""),
            "ts": ts,
            "source": source,
            "topic": topic,
        })
    return stories


def dedupe(stories):
    kept = []
    for s in stories:
        t = s["title"].lower()
        if not any(SequenceMatcher(None, t, k["title"].lower()).ratio() > 0.8 for k in kept):
            kept.append(s)
    return kept


def get_topic(topic: str):
    cached = _cache.get(topic)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]
    jobs = [(topic, url) for url in FEEDS[topic]]
    with ThreadPoolExecutor() as pool:
        results = list(pool.map(parse_feed, jobs))
    stories = [s for batch in results for s in batch]
    stories.sort(key=lambda s: s["ts"], reverse=True)
    stories = dedupe(stories)
    enrich(stories[:12])  # summarize only the top stories per topic
    _cache[topic] = (time.time(), stories)
    return stories


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/feed")
def feed(topic: str = "all", limit: int = 40):
    if topic == "all":
        # take one story from each topic in turn, so no topic dominates
        groups = [get_topic(t) for t in FEEDS]
        stories = [s for row in zip_longest(*groups) for s in row if s]
    elif topic in FEEDS:
        stories = get_topic(topic)
    else:
        stories = []
    stories = stories[:limit]
    return {"count": len(stories), "stories": stories}