import os
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

load_dotenv()

try:
    import anthropic
except ImportError:
    anthropic = None

API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-haiku-5-5"  # small, cheap model is plenty for blurbs
client = anthropic.Anthropic(api_key=API_KEY) if (anthropic and API_KEY) else None

_summaries: dict = {}  # link -> result, so each story is only summarized once

PROMPT = """You write short news blurbs. Based only on the headline and snippet below, reply with exactly two lines:
SUMMARY: <one or two plain sentences>
WHY: <one sentence on why this matters>
Do not add facts that are not in the text.

Headline: {title}
Snippet: {snippet}"""


def summarize_one(story):
    link = story["link"]
    if link in _summaries:
        return _summaries[link]
    result = {"ai_summary": "", "why": ""}
    if client:
        try:
            msg = client.messages.create(
                model=MODEL,
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": PROMPT.format(title=story["title"], snippet=story["summary"]),
                }],
            )
            for line in msg.content[0].text.splitlines():
                if line.startswith("SUMMARY:"):
                    result["ai_summary"] = line[8:].strip()
                elif line.startswith("WHY:"):
                    result["why"] = line[4:].strip()
        except Exception as e:
            print("summary failed:", e)
            return result  # don't cache failures, so it retries next time
    _summaries[link] = result
    return result


def enrich(stories):
    """Adds ai_summary and why to each story, in place."""
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(summarize_one, stories))
    for story, extra in zip(stories, results):
        story.update(extra)