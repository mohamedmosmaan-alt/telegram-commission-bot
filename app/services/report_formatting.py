"""
Turns one commission row (a dict of raw column -> raw value, exactly as
read from the sheet) into the label/value report text the customer
receives — matching the layout of the original Excel template tab
("Sheet2" in Fcc_Commission_New.xlsx) field for field, field order included.

Formatting rules, reverse-engineered from a real example row against its
rendered template:
  - Master, Gov, Area, Rep, SV, MGR, Category, Tiers -> shown as plain text
  - "%"  and "%2" -> shown as a rounded whole-number percentage (0.11 -> 11%)
  - every other field -> a money-like number: comma-separated, rounded to
    the nearest whole unit, and shown as "-" when the value is exactly 0
    (this is what the template does with untouched bonus/commission cells)
"""

# Order matters — this is the exact column order from the commission sheet,
# and therefore the exact order the report is sent in.
FIELD_ORDER = [
    "Master", "Gov", "Area", "Rep", "SV", "MGR", "Category",
    "Target 293", "293 MTD", "293 Expected Closing", "%",
    "Airtime MTD", "Airtime Expected Closing",
    "T 1 G 10%", "T 2 G 15%", "T 3 G 20%",
    "Bills MTD", "Bills Expected Closing",
    "MFI MTD", "MFI Expected Closing",
    "Fawry Pay MTD", "Fawry Pay Expected Closing",
    "Cashout MTD", "Cashout Closing",
    "293 Bonus", "Commission 10 %", "Commission 15 %", "Commission 20 %",
    "Total Airtime Commission", "Extra Bouns Cash Out",
    "MFI Deduction", "Fawry pay Deduction", "Net Bonus/Penalty",
    "240 MTD", "Total Transfer Target", "Total Transfer MTD",
    "Expected Transfer", "%2", "Tiers",
]

TEXT_FIELDS = {"Master", "Gov", "Area", "Rep", "SV", "MGR", "Category", "Tiers"}
PERCENT_FIELDS = {"%", "%2"}


def _to_number(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_value(field: str, value) -> str:
    if field in TEXT_FIELDS:
        return str(value) if value not in (None, "") else "—"

    number = _to_number(value)
    if number is None:
        return str(value) if value not in (None, "") else "—"

    if field in PERCENT_FIELDS:
        return f"{round(number * 100)}%"

    if number == 0:
        return "-"

    return f"{round(number):,}"


def format_commission_report(fields: dict) -> str:
    """
    `fields` is the raw dict for one master's row (whatever keys the sheet
    had — extra/renamed columns are simply skipped here since we don't know
    where to display them; FIELD_ORDER defines what's shown).
    """
    # case-insensitive lookup so a header typed as "master" or "MASTER" still matches
    lower_map = {str(k).strip().lower(): v for k, v in fields.items()}

    lines = []
    for field in FIELD_ORDER:
        raw_value = lower_map.get(field.lower())
        lines.append(f"<b>{field}</b>: {_format_value(field, raw_value)}")

    return "\n".join(lines)
