"""Financial label mapping and safe number parsing for table previews."""

import re


# Known variations let the analysis recognize labels from different companies.
ALIASES = {
    "revenue": [
        "revenue",
        "sales",
        "sales from operations",
        "revenue from operations",
        "turnover",
    ],
    "net_profit": [
        "net profit",
        "profit after tax",
        "profit for the year",
        "net income",
        "pat",
    ],
    "operating_cash_flow": [
        "operating cash flow",
        "cash flow from operating activities",
        "cash from operations",
    ],
    "current_assets": ["current assets"],
    "current_liabilities": ["current liabilities"],
}


# Normalize punctuation and case before comparing a document label with aliases.
def normalise_label(label: object) -> str:
    """Make a table label easy to compare with known financial aliases."""
    return re.sub(r"[^a-z0-9 ]", "", str(label).lower()).strip()


# Return a field suggestion without changing the original document.
def suggest_field(label: object) -> tuple[str | None, str]:
    """Return a transparent field suggestion for a document table label."""
    clean = normalise_label(label)
    for field, aliases in ALIASES.items():
        alias_found = any(alias in clean for alias in aliases)
        if alias_found:
            return field, "suggested"
    return None, "unmapped"


# Parse display values only for mapping; this function never invents missing units.
def parse_number(value: object) -> float | None:
    """Parse a table cell for mapping display without making financial claims."""
    if value is None or (isinstance(value, float) and value != value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip()
    missing_values = {"-", "—", "na", "n/a", "null"}
    if not raw or raw.lower() in missing_values:
        return None
    negative = raw.startswith("(") and raw.endswith(")")
    raw = raw.replace(",", "")
    raw = raw.replace("₹", "").replace("$", "").replace("%", "")
    raw = raw.strip("() ")
    raw = re.sub(r"[^0-9.\-]", "", raw)
    try:
        number = float(raw)
        return -number if negative else number
    except ValueError:
        return None
