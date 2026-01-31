from threading import Lock
from time import sleep


def downloading_info_thread(
    currently_downloading: dict[str, int], lock: Lock, finish: list[bool]
):
    """Download info thread
    This thread function prints information about the files that are currently downloaded. The lock is
    assigned to the `currently_downloading` dict. The `finish` list consists of exact one bool item.
    The thread stops working the this finish item becomes True. Otherwise it will print information
    every 100ms.
    """
    s = ""
    while not finish[0]:
        # first of all we have to put our cursor back to the start of the last string
        old_lines = s.count("\n")
        if old_lines:
            print(f"\033[{old_lines}F", end="", flush=True)
        s = ""  # we start with an empty string
        # now we can construct this string
        lock.acquire()
        for filename, p in currently_downloading.items():
            s += f"Downloading {filename}... {p}%\033[K\n"  # the line should end before the \n, so we use this ansi code here
        if len(currently_downloading) != 0:  # we can print the new information
            # but if we can't replace all old lines with new ones, because we have less lines generated than before
            # we have to clear the other lines
            new_lines = s.count("\n")
            if new_lines < old_lines:
                s += "\033[K\n" * (old_lines - new_lines)
            print(s, end="", flush=True)
        lock.release()
        sleep(0.1)
