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
