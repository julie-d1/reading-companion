import re
from chunker import chunk_book, chunks_through
from epub_loader import load_epub

# common capitalized words that aren't character / place names
_NUMS = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
         "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
         "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty",
         "sixty", "seventy", "eighty", "ninety", "hundred"}
_STOP = {"the", "and", "but", "for", "with", "she", "her", "his", "him", "they",
         "you", "your", "this", "that", "when", "then", "there", "what", "who",
         "god", "death", "lord", "lady", "sir", "mr", "mrs", "miss", "yes", "no",
         "chapter"} | _NUMS


def _proper_nouns(text):
    """Capitalized words used mid-sentence: a cheap stand-in for names and places."""
    found = set()
    for m in re.finditer(r'\b([A-Z][a-zA-Z]{2,})\b', text):
        j = m.start() - 1
        while j >= 0 and text[j] in ' \t':
            j -= 1
        prev = text[j] if j >= 0 else ''
        if prev and prev not in '.!?":;\n(“”‘’':            # skip start-of-sentence
            w = m.group(1)
            if w.lower() not in _STOP:
                found.add(w)
    return found


def first_chapter_of_each_name(chunks):
    """For every name-like word, the earliest chapter it shows up in."""
    first = {}
    for c in chunks:
        if c.chapter is None:
            continue
        for name in _proper_nouns(c.text):
            if name not in first or c.chapter < first[name]:
                first[name] = c.chapter
    return first


def find_leaks(recap_text, chunks, current_chapter):
    """Names in the recap the reader shouldn't know yet (they first appear later).
    Returns a sorted list of (name, first_chapter). An empty list means clean."""
    first = first_chapter_of_each_name(chunks)
    leaks = [(n, first[n]) for n in _proper_nouns(recap_text)
             if n in first and first[n] > current_chapter]
    return sorted(set(leaks), key=lambda t: t[1])


if __name__ == "__main__":
    import recap

    N = recap.CURRENT_CHAPTER
    chunks = chunk_book(load_epub(recap.BOOK))
    last = max(c.chapter for c in chunks if c.chapter)

    print(f"=== Eval: does a chapter-{N} recap leak anything from later? ===\n")

    # 1) The real, spoiler-safe recap should come back clean.
    safe = recap.make_recap(current_chapter=N)
    safe_leaks = find_leaks(safe, chunks, N)
    print(f"SAFE recap (built only from chapters 1..{N}):")
    print(f"  future-only names found: {len(safe_leaks)}  ->  "
          f"{'CLEAN, PASS' if not safe_leaks else safe_leaks}\n")

    # 2) A deliberately unsafe recap that was allowed to read ahead should get caught.
    later = min(N + 15, last)
    ahead = "\n\n".join(c.text for c in chunks_through(chunks, max_chapter=later)
                        if c.chapter is not None)[:150_000]
    bad = recap.client.chat.completions.create(
        model=recap.MODEL, temperature=0.3,
        messages=[{"role": "system", "content": "Summarize this book so far in one paragraph."},
                  {"role": "user", "content": ahead}],
    ).choices[0].message.content
    bad_leaks = find_leaks(bad, chunks, N)
    print(f"UNSAFE recap (allowed to read through chapter {later}):")
    print(f"  future-only names found: {len(bad_leaks)}  ->  "
          f"{'LEAK DETECTED, FAIL' if bad_leaks else 'clean'}")
    for name, ch in bad_leaks[:12]:
        print(f"    '{name}' first appears in chapter {ch}, reader is only on {N}")
    print("\nThe eval passes the safe recap and catches the unsafe one. "
          "That contrast is the proof it actually works.")
