import os
from openai import OpenAI
from dotenv import load_dotenv

from epub_loader import load_epub
from chunker import chunk_book, chunks_through

# ---- swap books here ----
BOOK = "Anathema.epub"
CURRENT_CHAPTER = 8           # the chapter you're on / fell asleep in
MODEL = "gpt-4o-mini"         # swap for any model 
MAX_CHARS = 350_000           # safety cap so a huge book can't overflow the model

load_dotenv()
client = OpenAI()             # reads OPENAI_API_KEY from .env / environment

SYSTEM = (
    "You help a reader remember what has happened in a novel so far. You are "
    "given the text of the book UP TO the reader's current point and nothing "
    "beyond it. Summarize only what is in that text. Never invent, infer, or "
    "hint at anything that is not explicitly there, and never foreshadow what "
    "might happen next."
)


def build_recap_context(book_path, current_chapter):
    """Everything the reader has read, up to current_chapter, as one string."""
    chunks = chunk_book(load_epub(book_path))
    allowed = chunks_through(chunks, max_chapter=current_chapter)
    if not allowed:
        raise SystemExit(
            f"No content found up to chapter {current_chapter}. "
            f"Check the chapter number and that '{book_path}' is in this folder."
        )
    text = "\n\n".join(c.text for c in allowed)
    trimmed = len(text) > MAX_CHARS
    if trimmed:
        text = text[-MAX_CHARS:]          # keep the most recent context if huge
    return text, allowed, trimmed


def make_recap(book_path=BOOK, current_chapter=CURRENT_CHAPTER):
    context, allowed, trimmed = build_recap_context(book_path, current_chapter)
    note = " (trimmed to recent events)" if trimmed else ""
    print(f"Recapping {book_path} up to chapter {current_chapter}: "
          f"{len(allowed)} chunks, {len(context):,} chars{note}\n")

    user = (
        f"Here is everything I've read so far, up to chapter {current_chapter}:\n\n"
        f"{context}\n\n"
        "Give me a spoiler-free recap of the story so far so I can pick up where "
        "I left off. Cover the main plot, the key characters, and where things "
        "stand right now. Keep it to a few short paragraphs."
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": user}],
        temperature=0.3,
    )
    return resp.choices[0].message.content


if __name__ == "__main__":
    print(make_recap())
