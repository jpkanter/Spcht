import sys
import time

from termcolor import colored


def is_dictkey(dictionary, *keys):
    try:
        for key in keys:
            if not key in dictionary:
                return False
        return True
    except TypeError:
        print("Non Dictionary provided", file=sys.stderr)


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


def sleepy_bar(sleep_time, timeskip=0.1):
    """
        Used more for debugging and simple programs, usage of time.sleep might be not accurate
        Displays a simple progressbar while waiting for time to tick away.
        :param float sleep_time: Time in seconds how long we wait, float for precision
        :param float timeskip: Time between cycles, very low numbers might not actualy happen
        :rtype: None
        :return: Doesnt return anything but prints to console with carriage return to overwrite itsself
    """
    try:
        start_time = time.time()
        stop_time = start_time + sleep_time
        while time.time() < stop_time:
            timenow = round(time.time() - start_time, 1)
            super_simple_progress_bar(timenow, sleep_time, prefix="Time", suffix=f"{timenow} / {sleep_time}")
            # i could have used time.time() and stop_time for the values of the bar as well
            time.sleep(timeskip)
        print("\n", end="")
    except KeyboardInterrupt:
        print(f"Aborting - {time.time()}")
        return True


def super_simple_progress_bar(current_value, max_value, prefix="", suffix="", out=sys.stdout):
    """
        Creates a simple progress bar without curses, overwrites itself everytime, will break when resizing
        or printing more text
        :param float current_value: the current value of the meter, if > max_value its set to max_value
        :param float max_value: 100% value of the bar, ints
        :param str prefix: Text that comes after the bar
        :param str suffix: Text that comes before the bar
        :param file out: output for the print, creator doesnt know why this exists
        :rtype: None
        :return: normalmente nothing, False and an error line printed instead of the bar
    """
    try:
        import shutil
    except ImportError:
        print("Import Error", file=out)
        return False
    try:
        current_value = float(current_value)
        max_value = float(max_value)
        prefix = str(prefix)
        suffic = str(suffix)
    except ValueError:
        print("Parameter Value error", file=out)
        return False
    if current_value > max_value:
        current_value = max_value  # 100%
    max_str, rows = shutil.get_terminal_size()
    del rows
    """
     'HTTP |======>                          | 45 / 256 '
     'HTTP |>                                 | 0 / 256 '
     'HTTP |================================| 256 / 256 '
     'HTTP |===============================>| 255 / 256 '
     '[ 5 ]1[ BAR BAR BAR BAR BAR BAR BAR BA]1[   10   ]'
    """
    bar_space = max_str - len(prefix) - len(suffix) - 3  # magic 3 for |, | and >
    bar_length = round((current_value/max_value)*bar_space)
    if bar_length == bar_space:
        arrow = "="
    else:
        arrow = ">"
    the_bar = "="*bar_length + arrow + " "*(bar_space-bar_length)
    print(prefix + "|" + the_bar + "|" + suffix, file=out, end="\r")


def super_simple_progress_bar_clear(out=sys.stdout):
    try:
        import shutil
    except ImportError:
        print("Import Error", file=out)
        return False
    max_str, rows = shutil.get_terminal_size()
    print(" "*max_str, end="\r")
