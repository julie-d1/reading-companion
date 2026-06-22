import re
import recap
from chunker import chunks_through


def define_word(chunks, word, current_chapter):
    """Return (explanation, passages_found). passages_found == 0 means not seen yet."""
    word = word.strip()
    allowed = chunks_through(chunks, max_chapter=current_chapter)
    pattern = re.compile(r'\b' + re.escape(word.lower()) + r'\b')
    hits = [c.text for c in allowed if pattern.search(c.text.lower())]

    if not hits:
        return (f"\u201c{word}\u201d hasn't come up yet in chapters 1\u2013{current_chapter}, "
                "so there's nothing you've read to explain it from. If it's an ordinary word "
                "you can look it up anywhere; if it's part of the story, you'll meet it soon."), 0

    context = "\n\n---\n\n".join(hits[:6])[:20000]
    system = ("You explain a word or term for someone reading a novel, using ONLY the passages "
              "they have read so far. Say what the word means in the context of this story. If "
              "it is an invented term, infer its meaning from how it is used. Never use anything "
              "from later in the book and never hint at what comes next. Keep it to 2 to 4 sentences.")
    user = (f'The reader asked about the word "{word}". Here are the passages where it appears '
            f'in what they have read:\n\n{context}\n\n'
            f'Explain what "{word}" means here.')
    r = recap.client.chat.completions.create(
        model=recap.MODEL, temperature=0.3,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    return r.choices[0].message.content, len(hits)
