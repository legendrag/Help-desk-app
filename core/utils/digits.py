"""Normalize Eastern Arabic / Persian digits to Western ASCII digits."""

_DIGIT_MAP = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩"  # Arabic-Indic
    "۰۱۲۳۴۵۶۷۸۹",  # Extended Arabic-Indic (Persian)
    "0123456789" * 2,
)


def normalize_digits(value):
    """Return *value* with Arabic/Persian digits mapped to 0-9.

    Non-string values are returned unchanged. Other characters are preserved.
    """
    if value is None or not isinstance(value, str):
        return value
    return value.translate(_DIGIT_MAP)
