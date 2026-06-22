import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Chunk:
    id: int                 # order in the book, 0 = the very start
    text: str
    chapter: int | None     # which chapter this chunk is in (None = front matter)
    char_start: int         # where this chunk starts in the full text
    char_end: int           # where it ends
    pct: float              # how far into the book it starts (0.0-1.0)


# A line that starts a chapter: "Chapter 12", "CHAPTER ONE", "Ch. 3",
# "Chapter Sixty-Two". We don't trust the printed number (some books label
# chapters differently in the table of contents than in the body) so we only
# use these matches to find WHERE chapters begin, and number them by order.
CHAPTER_RE = re.compile(
    r'^\s*(?:chapter|ch\.?)\s+(?:[0-9]{1,3}|[ivxlcdm]+|[a-z]+(?:[-\s][a-z]+)?)\b',
    re.IGNORECASE | re.MULTILINE,
)

# Headings packed closer than this, in a run this long, are a table of contents,
# not real chapters (a TOC lists every chapter with no story in between).
_PACKED_GAP = 600
_RUN_MIN = 4


def load_text(path: str) -> str:
    """Read a plain .txt book. (For an EPUB, extract it to .txt first with ebooklib.)"""
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def _chapter_starts(text):
    """Find where real chapters begin, as (char_offset, chapter_number) in order.

    Real-world mess this handles: a book often prints a table of contents at the
    front (every chapter listed back to back) plus stray lines like 'Chapter
    Heading Artwork'. Those show up as a tight cluster of headings with no story
    between them, so we drop any long packed run and keep only the headings that
    are spread out through the body, then number them by reading order.
    """
    offs = [m.start() for m in CHAPTER_RE.finditer(text)]
    n = len(offs)
    is_toc = [False] * n
    i = 0
    while i < n:                                   # find packed runs (a TOC)
        j = i
        while j + 1 < n and offs[j + 1] - offs[j] < _PACKED_GAP:
            j += 1
        if j - i + 1 >= _RUN_MIN:
            for k in range(i, j + 1):
                is_toc[k] = True
        i = j + 1

    starts = []
    num = 0
    for k in range(n):
        if is_toc[k]:
            continue
        num += 1
        starts.append((offs[k], num))
    return starts


def _chapter_for(offset, starts):
    """Which chapter does this character offset fall inside?"""
    current = None
    for start, number in starts:
        if offset >= start:
            current = number
        else:
            break
    return current


def chunk_book(text, target_chars: int = 1500):
    """
    Split the book into ordered chunks of about `target_chars`, breaking on
    paragraph boundaries so we never cut mid-sentence. Each chunk is tagged with
    its chapter, character range, and how far into the book it starts.

    A chunk never crosses a chapter line, so a chunk tagged 'chapter 1' can never
    secretly carry chapter 2 text that the spoiler filter would leak.
    """
    starts = _chapter_starts(text)
    total = len(text)
    chunks = []
    parts = []
    start_offset = None
    length = 0
    cid = 0

    def flush(end_offset):
        nonlocal parts, start_offset, length, cid
        body = "\n\n".join(parts).strip()
        parts, length = [], 0
        if not body or start_offset is None:
            start_offset = None
            return
        chunks.append(Chunk(
            id=cid,
            text=body,
            chapter=_chapter_for(start_offset, starts),
            char_start=start_offset,
            char_end=end_offset,
            pct=round(start_offset / total, 4) if total else 0.0,
        ))
        cid += 1
        start_offset = None

    for m in re.finditer(r'[^\n]+(?:\n[^\n]+)*', text):
        para = m.group().strip()
        if not para:
            continue
        para_chapter = _chapter_for(m.start(), starts)
        if start_offset is not None and para_chapter != _chapter_for(start_offset, starts):
            flush(m.start())
        if start_offset is None:
            start_offset = m.start()
        parts.append(para)
        length += len(para)
        if length >= target_chars:
            flush(m.end())
    flush(total)
    return chunks


def chunks_through(chunks, max_chapter=None, max_pct=None):
    """
    The spoiler boundary: keep only the chunks at or before the reader's spot.
    Everything past it stays invisible. Pass a chapter number (exact) or a
    percentage (approximate, chunk-granular).
    """
    out = chunks
    if max_chapter is not None:
        out = [c for c in out if c.chapter is not None and c.chapter <= max_chapter]
    if max_pct is not None:
        out = [c for c in out if c.pct <= max_pct]
    return out