def is_dictkey(dictionary, key):
    if key in dictionary:
        return True
    else:
        return False


def is_dict(variable):  # for all intends and purposes this is just an alias for isinstance
    return isinstance(variable, dict)

