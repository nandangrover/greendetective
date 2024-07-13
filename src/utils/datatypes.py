from re import sub
from typing import Dict

from django.db import models


def to_bool(value):
    valid = {
        "true": True,
        "t": True,
        "1": True,
        "false": False,
        "f": False,
        "0": False,
    }

    if isinstance(value, bool):
        return value

    lower_value = str(value).lower()
    return valid[lower_value] if lower_value in valid else False


def merge_dict(x, y, *args):
    z = x.copy()
    z.update(y)

    if len(args) > 0:
        for arg in args:
            z = merge_dict(z, arg)

    return z


def snake_case(s):
    return (
        "_".join(
            sub("([A-Z][a-z]+)", r" \1", sub("([A-Z]+)", r" \1", s.replace("-", " "))).split()
        )
        .lower()
        .replace("__", "_")
    )


def float_or_none(s):
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def int_or_none(s):
    try:
        return int(float_or_none(s))
    except (ValueError, TypeError):
        return None


def format_nested_errors(errors):
    if isinstance(errors, dict):
        return {k: format_nested_errors(v) for k, v in errors.items()}
    elif isinstance(errors, list):
        return [format_nested_errors(v) for v in errors]
    else:
        return str(errors)


def dict_values_are_empty(dictionary: Dict) -> bool:
    empty = True

    for value in dictionary.values():
        if isinstance(value, dict):
            if not dict_values_are_empty(value):
                empty = False

        elif value or value == 0:
            empty = False
    return empty


def is_file_field_empty(file_field: models.FileField) -> bool:
    if file_field is None:
        return True

    if file_field.name is None or file_field.name == "":
        return True

    return False
