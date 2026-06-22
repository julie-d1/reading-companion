import chromadb
from chunker import Chunk, load_text, chunk_book


def build_index(chunks: list[Chunk], name: str = "book",
                persist_dir: str = "./chroma", embedding_function=None):
    """Load chunks into a fresh Chroma collection, keyed by position metadata.

    Leaves embedding_function as None to use Chroma's built-in local model
    (downloads once on first run, no API key needed).
    """
    client = chromadb.PersistentClient(path=persist_dir)
    try:                                   # start clean so re-running won't duplicate
        client.delete_collection(name)
    except Exception:
        pass

    kwargs = {"name": name}
    if embedding_function is not None:
        kwargs["embedding_function"] = embedding_function
    col = client.create_collection(**kwargs)

    col.add(
        ids=[str(c.id) for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[{
            "chapter": c.chapter if c.chapter is not None else 0,   # 0 = front matter
            "pct": c.pct,
            "char_start": c.char_start,
        } for c in chunks],
    )
    return col


def _boundary(max_chapter=None, max_pct=None):
    """Build the Chroma metadata filter that enforces the spoiler line."""
    conds = []
    if max_chapter is not None:
        conds.append({"chapter": {"$lte": max_chapter}})
    if max_pct is not None:
        conds.append({"pct": {"$lte": max_pct}})
    if not conds:
        return None
    return conds[0] if len(conds) == 1 else {"$and": conds}


def all_through(col, max_chapter=None, max_pct=None) -> list[dict]:
    """Every chunk up to the reader's spot, back in reading order. Feeds the recap."""
    res = col.get(where=_boundary(max_chapter, max_pct))
    rows = [{"text": d, "char_start": m["char_start"], "chapter": m["chapter"]}
            for d, m in zip(res["documents"], res["metadatas"])]
    rows.sort(key=lambda r: r["char_start"])
    return rows


def search_through(col, query: str, max_chapter=None, max_pct=None,
                   k: int = 5) -> list[dict]:
    """Top-k chunks relevant to `query`, but only from what the reader has reached.
    Feeds vocab-in-context and the discussion feature."""
    res = col.query(query_texts=[query],
                    where=_boundary(max_chapter, max_pct),
                    n_results=k)
    return [{"text": d, "char_start": m["char_start"], "chapter": m["chapter"]}
            for d, m in zip(res["documents"][0], res["metadatas"][0])]


if __name__ == "__main__":
    sample = (
        "Chapter 1\n\n"
        "Violet stepped into the courtyard. The dragons watched from the cliffs above.\n\n"
        "She had trained her whole life for this one moment.\n\n"
        "Chapter 2\n\n"
        "The gauntlet stretched ahead. Her brother Brennan is secretly still alive.\n\n"
        "Xaden waited at the far end, arms crossed.\n\n"
    )
    chunks = chunk_book(sample, target_chars=80)
    col = build_index(chunks, persist_dir="./chroma_demo")

    print("RECAP MATERIAL up to chapter 1 (everything the reader has read):")
    for r in all_through(col, max_chapter=1):
        print(f"  ch{r['chapter']}: {r['text'][:60]!r}")

    print("\nSEARCH 'is Brennan alive?' limited to chapter 1:")
    for h in search_through(col, "is Brennan alive?", max_chapter=1, k=3):
        print(f"  ch{h['chapter']}: {h['text'][:60]!r}")
    print("  ^ the chapter 2 reveal about Brennan is filtered out.")
