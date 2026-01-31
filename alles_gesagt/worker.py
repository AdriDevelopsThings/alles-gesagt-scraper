from dataclasses import dataclass
from os import rename
from os.path import join, split
from queue import Empty, Queue
from threading import Lock

import requests

from alles_gesagt.episodes import Episode


@dataclass
class WorkerQueueElement:
    episode: Episode
    filename: str
    display_filename: str


def worker(
    queue: Queue[WorkerQueueElement],
    currently_downloading: dict[str, int],
    lock: Lock,
    finish: list[bool],
):
    """Download worker
    This worker gets an element from the queue, download this element and puts
    download information in the `currently_downloading` dict. The function of the lock
    is to prevent that two threads doing weird things at `currently_downloading` at the same time.
    The finish value is a list with one element which contains if we are finished or not
    """
    while not finish[0]:
        try:
            i = queue.get(timeout=1)
        except Empty:
            continue
        lock.acquire()
        # 0% downloaded at start
        currently_downloading[i.display_filename] = 0
        lock.release()
        response = requests.get(i.episode.url, stream=True)
        response.raise_for_status()
        length = int(response.headers["content-length"])
        written = 0
        dir, filename = split(i.filename)
        tmp_filename = join(dir, "." + filename + ".downloading")
        with open(tmp_filename, "wb") as file:
            # split content in 64 KB chunks
            for chunk in response.iter_content(1024 * 64):
                file.write(chunk)
                written += len(chunk)
                percent = round((written / length) * 100)
                lock.acquire()
                currently_downloading[i.display_filename] = percent
                lock.release()
        rename(tmp_filename, i.filename)
        # download is finished
        lock.acquire()
        del currently_downloading[i.display_filename]
        lock.release()
        queue.task_done()
