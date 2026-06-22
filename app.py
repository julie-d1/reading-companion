import os
import html
import streamlit as st

import recap                       # the configured OpenAI client + settings live here
from chunker import chunk_book, chunks_through
from epub_loader import load_epub
from leak_test import find_leaks
from vocab import define_word
from visualize import visualize_scene
from discuss import answer as discuss_answer
from book_index import build_index
from chromadb.utils import embedding_functions

BOOK = recap.BOOK
ACCENT = "#B7553F"   # ember
SEALED = "#101714"   # shadow (the unread part of the book)
PANEL = "#182420"
BONE = "#E8E2D2"
FOG = "#9AA39A"
SAFE = "#6FAE8E"
LEAK = "#C9584D"

st.set_page_config(page_title="Catch me up", page_icon="🜂", layout="centered")


@st.cache_data(show_spinner=False)
def get_chunks(path):
    return chunk_book(load_epub(path))


@st.cache_resource(show_spinner="Indexing the book for discussion…")
def get_index(_chunks, book_path):
    ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.environ.get("OPENAI_API_KEY"), model_name="text-embedding-3-small")
    return build_index(_chunks, name="discuss", embedding_function=ef)


def recap_up_to(chunks, n):
    text = "\n\n".join(c.text for c in chunks_through(chunks, max_chapter=n))
    if len(text) > recap.MAX_CHARS:
        text = text[-recap.MAX_CHARS:]
    user = (f"Here is everything I've read so far, up to chapter {n}:\n\n{text}\n\n"
            "Give me a spoiler-free recap of the story so far so I can pick up where I "
            "left off. Cover the main plot, the key characters, and where things stand "
            "right now. Keep it to a few short paragraphs.")
    r = recap.client.chat.completions.create(
        model=recap.MODEL, temperature=0.3,
        messages=[{"role": "system", "content": recap.SYSTEM},
                  {"role": "user", "content": user}])
    return r.choices[0].message.content


def unsafe_recap(chunks):
    # No spoiler guard: let it read all the way to the end, where the big reveals live.
    whole = "\n\n".join(c.text for c in chunks if c.chapter is not None)
    tail = whole[-150_000:]
    r = recap.client.chat.completions.create(
        model=recap.MODEL, temperature=0.3,
        messages=[{"role": "system", "content":
                   "Recap this novel for a reader, including how things turn out. One short "
                   "paragraph, and name the key characters involved."},
                  {"role": "user", "content": tail}])
    return r.choices[0].message.content


def badge(ok, msg):
    color = SAFE if ok else LEAK
    mark = "✓" if ok else "✗"
    st.markdown(
        f"<div style='display:inline-block;padding:.5rem .9rem;border-radius:999px;"
        f"background:{color}22;color:{color};border:1px solid {color}66;"
        f"font-weight:600;font-size:.95rem;'>{mark}&nbsp; {html.escape(msg)}</div>",
        unsafe_allow_html=True)


def boundary_bar(n, last):
    pct = round(n / last * 100, 1)
    st.markdown(
        f"<div style='display:flex;height:12px;border-radius:6px;overflow:hidden;"
        f"border:1px solid #2A3A33;margin:.3rem 0 .35rem;'>"
        f"<div style='width:{pct}%;background:{ACCENT};'></div>"
        f"<div style='width:{100 - pct}%;background:{SEALED};'></div></div>",
        unsafe_allow_html=True)


def card(text):
    body = html.escape(text).replace("\n", "<br>")
    st.markdown(
        f"<div style='background:{PANEL};border:1px solid #2A3A33;border-left:3px solid {ACCENT};"
        f"border-radius:8px;padding:1.1rem 1.3rem;line-height:1.65;color:{BONE};'>{body}</div>",
        unsafe_allow_html=True)


# ---------------- page ----------------
chunks = get_chunks(BOOK)
last = max(c.chapter for c in chunks if c.chapter)

st.markdown(f"<div style='letter-spacing:.25em;color:{FOG};font-size:.8rem;'>READING COMPANION</div>",
            unsafe_allow_html=True)
st.markdown("<h1 style='margin:.1rem 0 .2rem;font-size:2.7rem;'>Catch me up.</h1>",
            unsafe_allow_html=True)
st.markdown(f"<p style='color:{FOG};margin-top:0;'>Everything you've read in "
            f"<em>{html.escape(BOOK.replace('.epub', ''))}</em>, and not one word more.</p>",
            unsafe_allow_html=True)

st.write("")
n = st.slider("Where are you?", 1, last, min(8, last))
st.markdown(f"<div style='color:{BONE};'>You've read through <b>chapter {n}</b> of {last}.</div>",
            unsafe_allow_html=True)
boundary_bar(n, last)
st.caption(f"Read: chapters 1–{n}.   Sealed: {min(n + 1, last)}–{last}.")

st.write("")
tab_recap, tab_vocab, tab_viz, tab_discuss = st.tabs(
    ["Catch me up", "Define a word", "Visualize", "Discuss"])

with tab_recap:
    if st.button("Catch me up", type="primary", key="recap_btn"):
        with st.spinner(f"Reading up to chapter {n}…"):
            text = recap_up_to(chunks, n)
        st.session_state["result"] = {"n": n, "text": text, "leaks": find_leaks(text, chunks, n)}

    res = st.session_state.get("result")
    if res:
        st.write("")
        if res["leaks"]:
            nm, ch = res["leaks"][0]
            badge(False, f"Leak — '{nm}' first appears in chapter {ch}")
        else:
            badge(True, f"Spoiler-safe — checked against all {last} chapters, nothing leaked")
        st.write("")
        card(res["text"])
        st.caption(f"Built only from chapters 1–{res['n']}. The model never received the rest.")

    st.write("")
    with st.expander("Prove the guard actually works"):
        st.write("Generate a recap that's allowed to read ahead, then run the same leak-check on it.")
        if st.button("Show what happens without the guard", key="guard_btn"):
            with st.spinner("Letting it read to the end…"):
                bad = unsafe_recap(chunks)
            bad_leaks = find_leaks(bad, chunks, n)
            if bad_leaks:
                nm, ch = bad_leaks[0]
                badge(False, f"Leak caught — '{nm}' first appears in chapter {ch}, you're on {n}")
            else:
                badge(True, "No leak this time — try an earlier chapter")
            st.write("")
            card(bad)

with tab_vocab:
    st.write("Wondering what a word or a bit of lore means? Get it explained from only "
             "what you've read, no spoilers.")
    with st.form("vocab_form"):
        word = st.text_input("Word or term", key="vocab_word", placeholder="e.g. Banishing")
        submitted = st.form_submit_button("What does it mean?")
    if submitted and word.strip():
        with st.spinner("Looking it up in what you've read…"):
            explanation, found = define_word(chunks, word, n)
        st.session_state["vocab"] = {"word": word, "n": n, "text": explanation, "found": found}

    v = st.session_state.get("vocab")
    if v:
        st.write("")
        card(v["text"])
        if v["found"]:
            st.caption(f"Explained only from chapters 1–{v['n']} · found in {v['found']} "
                       f"passage{'s' if v['found'] != 1 else ''} you've read.")
        else:
            st.caption(f"Checked chapters 1–{v['n']}.")

with tab_viz:
    st.write("Picture a character or place the way the book has described them so far. "
             "Nothing from later can show up.")
    with st.form("viz_form"):
        col1, col2 = st.columns([3, 2])
        with col1:
            subject = st.text_input("Character or place", key="viz_subject", placeholder="e.g. Maevyth")
        with col2:
            style = st.selectbox("Style", ["Photorealistic", "Illustrated"], key="viz_style")
        submitted = st.form_submit_button("Picture it")
    if submitted and subject.strip():
        with st.spinner("Reading the descriptions and drawing…"):
            try:
                image, prompt, found = visualize_scene(chunks, subject, n, style.lower())
                st.session_state["viz"] = {"subject": subject, "n": n, "image": image,
                                           "prompt": prompt, "found": found, "error": None}
            except Exception as e:
                st.session_state["viz"] = {"subject": subject, "n": n, "error": str(e)}

    z = st.session_state.get("viz")
    if z:
        st.write("")
        if z.get("error"):
            badge(False, "Couldn't draw that one")
            st.caption(html.escape(z["error"][:200]))
        elif not z.get("found"):
            card(f"\u201c{z['subject']}\u201d hasn't appeared yet in chapters 1\u2013{z['n']}, so "
                 "there's nothing described to draw. Try a character or place you've already met.")
        else:
            st.image(z["image"], use_container_width=True)
            st.caption(f"Drawn only from chapters 1–{z['n']} · based on {z['found']} "
                       f"passage{'s' if z['found'] != 1 else ''} you've read.")
            with st.expander("See the description it drew from"):
                st.write(z["prompt"])

with tab_discuss:
    st.write(f"Talk it through. Ask about characters, motives, theories. It only knows "
             f"what you've read up to chapter {n}.")
    history = st.session_state.setdefault("chat", [])
    for m in history:
        with st.chat_message(m["role"]):
            st.write(m["content"])
    q = st.chat_input("Ask about the book…")
    if q:
        history.append({"role": "user", "content": q})
        with st.chat_message("user"):
            st.write(q)
        with st.chat_message("assistant"):
            try:
                with st.spinner("Thinking…"):
                    col = get_index(chunks, BOOK)
                    a = discuss_answer(col, history[:-1], q, n)
            except Exception as e:
                a = f"Something went wrong: {str(e)[:200]}"
            st.write(a)
        history.append({"role": "assistant", "content": a})
