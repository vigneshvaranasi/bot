import re


def sanitize_markdown_output(text: str) -> str:
    """
    Remove fenced code blocks (``` or ```lang) from the output while preserving inner content.
    Also strips stray triple backticks if present.
    """
    if not text:
        return text

    # Replace fenced code blocks with their inner content
    # Handles cases like ```markdown\n...\n``` or ```\n...\n```
    pattern = re.compile(r"```[a-zA-Z0-9_-]*\n?([\s\S]*?)\n?```", re.MULTILINE)
    while True:
        new_text = re.sub(pattern, r"\1", text)
        if new_text == text:
            break
        text = new_text

    text = text.replace("```", "")

    return text.strip()
