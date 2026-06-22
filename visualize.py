import re
import base64
import recap
from chunker import chunks_through

IMAGE_MODEL = "gpt-image-2"
IMAGE_QUALITY = "medium"  # "low" ~2c, "medium" ~7c, "high" ~15-20c per image

_STOP = {"the", "a", "an", "of", "and", "in", "on", "at", "to", "with", "her", "his"}

_STYLES = {
    "photorealistic": ("a photorealistic, cinematic photograph: natural skin texture, realistic "
                       "lighting, shallow depth of field, richly detailed and lifelike"),
    "illustrated": ("a painterly, atmospheric digital illustration: rich detail, dramatic "
                    "lighting, expressive and cinematic"),
}


def _visual_prompt(subject, passages, style):
    """Distill a spoiler-safe, flattering image prompt from the read passages."""
    context = "\n\n---\n\n".join(passages[:6])[:16000]
    look = _STYLES.get(style, _STYLES["photorealistic"])
    system = (
        "You write an image-generation prompt for a character or place from a novel, using ONLY "
        "the details in the passages provided.\n"
        "- Describe appearance and setting exactly as written. If a detail isn't in the passages, "
        "leave it out rather than invent it, and use nothing from outside the passages.\n"
        "- Preserve the impression the prose gives. If the character is described as beautiful, "
        "handsome, striking, or alluring, make that the centerpiece of the prompt. Render dark, "
        "unusual, or marked features (an aura, scars, strange eyes, pale skin) as part of a "
        "striking and attractive appearance, never as monstrous, grotesque, or frightening, "
        "unless the text clearly frames them that way.\n"
        f"- Render it as {look}.\n"
        "- Output one vivid prompt of 2 to 4 sentences for a flattering, high-quality portrait "
        "with cinematic lighting."
    )
    user = (f'Subject: "{subject}". Passages the reader has seen:\n\n{context}\n\n'
            f'Write the image prompt for "{subject}".')
    r = recap.client.chat.completions.create(
        model=recap.MODEL, temperature=0.4,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    return r.choices[0].message.content.strip()


def visualize_scene(chunks, subject, current_chapter, style="photorealistic"):
    """Return (image, prompt, passages_found).

    `image` is raw PNG bytes (GPT image models) or a URL string (older models),
    both of which st.image() displays. It's None if the subject isn't seen yet.
    """
    subject = subject.strip()
    allowed = chunks_through(chunks, max_chapter=current_chapter)
    words = [w for w in re.findall(r'[a-z]+', subject.lower()) if w not in _STOP]
    if not words:
        return None, None, 0
    hits = [c.text for c in allowed
            if all(re.search(r'\b' + w + r'\b', c.text.lower()) for w in words)]
    if not hits:
        return None, None, 0

    prompt = _visual_prompt(subject, hits, style)
    resp = recap.client.images.generate(model=IMAGE_MODEL, prompt=prompt,
                                        size="1024x1024", quality=IMAGE_QUALITY, n=1)
    item = resp.data[0]
    image = item.url if getattr(item, "url", None) else base64.b64decode(item.b64_json)
    return image, prompt, len(hits)
