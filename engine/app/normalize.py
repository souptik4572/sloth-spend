"""Merchant normalisation (spec §7.4).

M3: the deterministic pre-clean (`desc_key`) that import needs to store every transaction.
M4 adds the Gemma batches, the cache in merchant_map and the rule fallback.
"""

import re

CATEGORIES = ["Streaming", "Music", "Software", "Cloud Storage", "Fitness", "News & Media", "Telecom",
              "Utilities", "Insurance", "Housing", "Food Delivery", "Groceries", "Dining", "Transport",
              "Shopping", "Travel", "Health", "Education", "Transfers", "Fees", "Other"]

NOISE = [
    r"\b\d{0,6}[X\*]{3,}\d{0,6}\b",  # card masks inside one token, e.g. 4160XXXX2291 (added to §7.4)
    r"\b(POS|ACH|DEBIT|CREDIT|CARD|PURCHASE|RECURRING|PAYMENT|ONLINE|ECOM|NEFT|IMPS|UPI|VISA|MASTERCARD|TXN|REF)\b",
    r"\b[X\*]{2,}\d{2,4}\b",
    r"\b\d{4,}\b",
    r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b",
    r"#\S+",
    r"[^A-Z0-9&\.\* ]",
]


def desc_key(raw: str) -> str:
    s = raw.upper()
    for pattern in NOISE:
        s = re.sub(pattern, " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return (s or raw.upper())[:60]
