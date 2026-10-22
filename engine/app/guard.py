"""No invented contact details (spec DoD 4): links, email addresses and phone numbers never reach the user.

The prompts already forbid them; this is the net under the prompts for Ask Sloth answers and drafts.
"""

import re

URL = re.compile(r"(?i)\b(?:https?://|www\.)\S+|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|co|in|app|tv|uk)"
                 r"(?:/\S*)?\b")
EMAIL = re.compile(r"(?i)\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
# Digit runs with phone separators. Money ($49.99, 1,18,450.20) and dates are excluded below.
PHONE = re.compile(r"(?<![\w$₹€£.,/])\+?\(?\d[\d\s().-]{5,}\d(?![\w/])")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _is_phone(candidate: str) -> bool:
    digits = sum(c.isdigit() for c in candidate)
    return digits >= 7 and not ISO_DATE.search(candidate)


def find_contacts(text: str) -> list[str]:
    found = EMAIL.findall(text)
    stripped = EMAIL.sub(" ", text)
    found += URL.findall(stripped)
    found += [m.group(0) for m in PHONE.finditer(URL.sub(" ", stripped)) if _is_phone(m.group(0))]
    return found


def scrub(text: str) -> str:
    """Replace any link, email address or phone number with a plain pointer to where the user can look."""
    text = EMAIL.sub("the support address on your receipt", text)
    text = URL.sub("the merchant’s website", text)
    return PHONE.sub(lambda m: "the number on your receipt" if _is_phone(m.group(0)) else m.group(0), text)


# "I've set a reminder" when no tool confirmed it (small models do this): the answer must not claim an action.
CLAIM = re.compile(r"(?i)\b(i['’]ve|i have|i|i['’]ll|i will)\s+(set|scheduled|created|added)\b[^.!?]*\bremind"
                   r"|\breminder\b[^.!?]*\b(is|has been|was|is now)\s+(set|scheduled|created|on)\b")
NEGATION = re.compile(r"(?i)\b(no|not|n['’]t|cannot|unable|isn['’]t|wasn['’]t|couldn['’]t|can['’]t)\b")


def claims_reminder(text: str) -> bool:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return any(CLAIM.search(s) and not NEGATION.search(s) for s in sentences)
