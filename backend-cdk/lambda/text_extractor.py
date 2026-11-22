import re

def extract_text(html, max_tokens=30000):
    # Remove all tags
    text = re.sub(r'<[^>]+>', ' ', html)

    # Convert HTML entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&#160;', ' ')

    # Normalize whitespace
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        stripped = ' '.join(line.split())
        if stripped:
            clean_lines.append(stripped)
    clean_text = "\n".join(clean_lines)

    # Estimate tokens (1 token = ~4 characters)
    estimated_tokens = len(clean_text) // 4

    if estimated_tokens <= max_tokens:
        return clean_text

    # Truncate to fit budget
    max_chars = max_tokens * 4
    return clean_text[:max_chars]