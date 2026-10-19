"""Turn a screenshot into searchable text with Claude vision."""
from . import config, llm

SYSTEM = ("You describe screenshots from a software help center so they can be searched later. "
          "List every visible menu name, button, field label, setting name, and value you can read. "
          "Then say in one sentence what the screenshot demonstrates. Max 120 words. No guessing beyond what is visible.")


async def describe_image(src: str, alt: str, page_title: str) -> str:
    content = [
        {"type": "image", "source": {"type": "url", "url": src}},
        {"type": "text", "text": f"Article: {page_title}\nAlt text: {alt or '(none)'}\nDescribe this screenshot."},
    ]
    return (await llm.call(config.MODEL_VISION, SYSTEM, content, max_tokens=300, label="vision")).strip()
