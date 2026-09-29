import pytest
from app.services.phone import normalize_phone, try_normalize_phone, PhoneNormalizationError


@pytest.mark.parametrize("raw", [
    "01012345678",
    "+201012345678",
    "201012345678",
    "010 1234 5678",
    "0020 10 1234 5678",
    "+20 10 1234 5678",
])
def test_various_formats_normalize_to_same_number(raw):
    assert normalize_phone(raw) == "+201012345678"


def test_landline_or_invalid_prefix_is_rejected():
    # "03" is a landline area code in Egypt, not a mobile prefix
    with pytest.raises(PhoneNormalizationError):
        normalize_phone("0212345678")


def test_empty_input_raises():
    with pytest.raises(PhoneNormalizationError):
        normalize_phone("")


def test_garbage_input_raises():
    with pytest.raises(PhoneNormalizationError):
        normalize_phone("not a phone number")


def test_try_normalize_returns_none_on_failure():
    assert try_normalize_phone("garbage") is None
    assert try_normalize_phone("01012345678") == "+201012345678"
