import re
from collections import Counter

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "to", "of", "in", "on", "for", "and", "or", "but", "with",
    "as", "at", "by", "from", "that", "this", "it", "its",
    "has", "have", "had", "will", "would", "could", "should",
    "after", "before", "about", "into", "over", "under",
    "their", "they", "them", "he", "she", "his", "her",
    "who", "what", "when", "where", "which", "while",
}


def tokenize(text):
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    return [word for word in words if word not in STOPWORDS]


def split_sentences(text):
    return [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", text or "")
        if len(s.strip()) > 20
    ]


def summarize_one(story):
    title = story.get("title", "")
    description = story.get("summary", "")

    sentences = split_sentences(description)

    # Fallback when RSS description is missing
    if not sentences:
        summary = title
    else:
        words = tokenize(description)
        frequencies = Counter(words)

        title_words = set(tokenize(title))

        scored = []

        for index, sentence in enumerate(sentences):
            sentence_words = tokenize(sentence)

            if not sentence_words:
                continue

            score = sum(
                frequencies[word] for word in sentence_words
            ) / len(sentence_words)

            # Give preference to sentences related to the headline
            overlap = len(set(sentence_words) & title_words)

            score += overlap * 0.5

            # Slight preference for earlier sentences
            score += 1 / (index + 1)

            scored.append((score, index, sentence))

        scored.sort(reverse=True)

        selected = sorted(scored[:2], key=lambda x: x[1])

        summary = " ".join(item[2] for item in selected)

    # Basic explanation without external AI
    keywords = tokenize(title)

    if keywords:
        topic = " ".join(keywords[:3])
        why = (
            f"This update may be useful for readers "
            f"following {topic}."
        )
    else:
        why = "This provides an update on the reported news."

    return {
        "ai_summary": summary,
        "why": why
    }


def enrich(stories):
    """Adds summaries and relevance explanations to stories."""

    for story in stories:
        extra = summarize_one(story)
        story.update(extra)