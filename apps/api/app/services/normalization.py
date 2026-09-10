import re
import unicodedata


def normalize_name(value: str) -> str:
    stripped = value.strip().lower()
    collapsed = re.sub(r"\s+", " ", stripped)
    decomposed = unicodedata.normalize("NFKD", collapsed)
    return "".join(character for character in decomposed if not unicodedata.combining(character))
