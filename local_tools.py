from termcolor import colored


def is_dictkey(dictionary, key):
    if key in dictionary:
        return True
    else:
        return False


def is_dict(variable):  # for all intends and purposes this is just an alias for isinstance
    return isinstance(variable, dict)


def cprint_type(object, show_type=False):
    # debug function, prints depending on variable type
    colors = {
        "str": "green",
        "dict": "yellow",
        "list": "cyan",
        "float": "white",
        "int": "grey",
        "tuple": "blue",
        "unknow_object": "magenta"
    }

    if isinstance(object, str):
        color = "str"
    elif isinstance(object, dict):
        color = "dict"
    elif isinstance(object, list):
        color = "list"
    elif isinstance(object, float):
        color = "float"
    elif isinstance(object, int):
        color = "int"
    elif isinstance(object, tuple):
        color = "tuple"
    else:
        color = "unknow_object"

    prefix = "{}:".format(color)
    if not show_type:
        prefix = ""

    print(prefix, colored(object, colors.get(color, "white")))


def list_has_elements(iterable):
    # technically this can check more than lists, but i use it to check some crude object on having objects or not
    for item in iterable:
        return True
    return False