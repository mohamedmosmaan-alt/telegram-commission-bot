"""
Phone number normalization.

Goal (§8): turn any reasonable input format into one canonical form,
E.164-style: "+201012345678".

Supported input examples for Egypt (country code 20):
    01012345678
    +201012345678
    201012345678
    010 1234 5678
    +20 10 1234 5678
    0020 10 12345678

The design is intentionally table-driven (COUNTRY_RULES) so adding another
country later means adding one entry, not rewriting the function.
"""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CountryRule:
    country_code: str          # e.g. "20"
    trunk_prefix: str          # the leading "0" used domestically, e.g. "0"
    national_number_length: int  # digits in the number AFTER the trunk 0 is stripped
    mobile_prefixes: tuple[str, ...]  # valid mobile leading digits, for basic sanity-checking


# Egyptian mobile numbers: 010/011/012/015 + 8 digits = 10 digits after the leading 0
EGYPT = CountryRule(
    country_code="20",
    trunk_prefix="0",
    national_number_length=10,
    mobile_prefixes=("10", "11", "12", "15"),
)

COUNTRY_RULES: dict[str, CountryRule] = {
    "20": EGYPT,
}


class PhoneNormalizationError(ValueError):
    pass


def _strip_non_digits(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def normalize_phone(raw: str, default_country_code: str = "20") -> str:
    """
    Normalize a raw phone string to "+<countrycode><nationalnumber>".
    Raises PhoneNormalizationError if the input can't be confidently normalized.
    """
    if not raw or not raw.strip():
        raise PhoneNormalizationError("Empty phone number.")

    digits = _strip_non_digits(raw)
    if not digits:
        raise PhoneNormalizationError("No digits found in input.")

    rule = COUNTRY_RULES.get(default_country_code)
    if rule is None:
        raise PhoneNormalizationError(f"Unsupported country code: {default_country_code}")

    cc = rule.country_code

    # Case 1: "00" international prefix, e.g. 0020101234...
    if digits.startswith("00" + cc):
        digits = digits[2:]  # drop the "00", leaves "20..."

    # Case 2: already has country code without plus, e.g. 20101234...
    if digits.startswith(cc) and len(digits) == len(cc) + rule.national_number_length:
        national = digits[len(cc):]
    # Case 3: local format with trunk 0, e.g. 0101234...
    elif digits.startswith(rule.trunk_prefix) and len(digits) == len(rule.trunk_prefix) + rule.national_number_length:
        national = digits[len(rule.trunk_prefix):]
    # Case 4: local format without trunk 0 (rare, e.g. shared verbally), e.g. 101234...
    elif len(digits) == rule.national_number_length:
        national = digits
    else:
        raise PhoneNormalizationError(
            f"Could not normalize '{raw}': unexpected length/format for country code +{cc}."
        )

    if rule.mobile_prefixes and not national.startswith(rule.mobile_prefixes):
        raise PhoneNormalizationError(
            f"'{raw}' does not look like a valid mobile number for +{cc}."
        )

    return f"+{cc}{national}"


def try_normalize_phone(raw: str, default_country_code: str = "20") -> str | None:
    """Same as normalize_phone but returns None instead of raising."""
    try:
        return normalize_phone(raw, default_country_code)
    except PhoneNormalizationError:
        return None
