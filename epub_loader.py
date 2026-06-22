import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup


def load_epub(path: str) -> str:
    book = epub.read_epub(path)
    parts = []
    for entry in book.spine:                              # spine = reading order
        idref = entry[0] if isinstance(entry, (tuple, list)) else entry
        item = book.get_item_with_id(idref)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        if isinstance(item, (epub.EpubNav,)):             # skip the table-of-contents page
            continue
        soup = BeautifulSoup(item.get_content(), "html.parser")
        for junk in soup(["script", "style"]):            # drop non-text
            junk.decompose()
        text = soup.get_text("\n")                        # newline between blocks
        text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


if __name__ == "__main__":
    import sys, glob
    found = sys.argv[1] if len(sys.argv) > 1 else next(iter(glob.glob("*.epub")), None)
    if not found:
        print("No .epub found. Put one in this folder, or run: python epub_loader.py yourbook.epub")
    else:
        text = load_epub(found)
        print(f"Loaded '{found}': {len(text):,} characters.\n")
        print("First 400 characters:\n")
        print(text[:400])