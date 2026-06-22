import recap
from book_index import search_through

SYSTEM = (
    "You are a thoughtful book-club partner discussing a novel with a reader. You may use ONLY "
    "the passages provided and what the reader has read up to their current chapter. Rules:\n"
    "- Ground what you say in the provided passages. Do not use any outside knowledge of this "
    "book or its plot.\n"
    "- Never reveal, confirm, or hint at anything that happens after the reader's current "
    "chapter. If a question needs later information, say it hasn't happened yet in their reading "
    "and you can't say without spoiling.\n"
    "- You can analyze characters, motives, relationships, and themes, and you can theorize, but "
    "frame any theory as an open question, never as a known outcome.\n"
    "- Be conversational and concise."
)


def answer(col, history, question, current_chapter, k=8):
    """history is the prior [{'role','content'}, ...] turns (without this question)."""
    passages = search_through(col, question, max_chapter=current_chapter, k=k)
    context = "\n\n---\n\n".join(p["text"] for p in passages) if passages else "(no passages found)"
    system = (SYSTEM + f"\n\nThe reader is on chapter {current_chapter}. Relevant passages from "
              f"what they have read:\n\n{context}")
    messages = [{"role": "system", "content": system}] + history + \
               [{"role": "user", "content": question}]
    r = recap.client.chat.completions.create(model=recap.MODEL, temperature=0.5, messages=messages)
    return r.choices[0].message.content
