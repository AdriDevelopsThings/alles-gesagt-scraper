from argparse import ArgumentParser
from os import listdir, mkdir, remove
from os.path import exists, join
from queue import Empty, Queue
from threading import Lock, Thread
from time import sleep

import requests
from bs4 import BeautifulSoup

from alles_gesagt.download_info import downloading_info_thread
from alles_gesagt.episodes import query_episodes
from alles_gesagt.worker import WorkerQueueElement, worker

parser = ArgumentParser()
parser.add_argument("-w", "--worker-count", type=int, default=4)
parser.add_argument(
    "-o",
    "--output",
    default="episodes",
    help="Destination where episodes should be saved",
)


def cleanup_downloading(dir: str) -> None:
    for file in listdir(dir):
        if file.endswith(".downloading"):
            print(f"Cleaning up tmp file {file}")
            remove(join(dir, file))


def main() -> None:
    args = parser.parse_args()
    # create the output directory if it does not exist
    if not exists(args.output):
        mkdir(args.output)
    cleanup_downloading(args.output)

    # create thread variables
    currently_downloading_lock = Lock()
    currently_downloading: dict[str, int] = {}
    queue: Queue[WorkerQueueElement] = Queue()
    finish = [False]
    finish_info = [False]

    # construct threads and start them
    threads = []
    for i in range(args.worker_count):
        thread = Thread(
            target=worker,
            args=(queue, currently_downloading, currently_downloading_lock, finish),
        )
        thread.start()
        threads.append(thread)
    di_thread = Thread(
        target=downloading_info_thread,
        args=(currently_downloading, currently_downloading_lock, finish_info),
    )
    di_thread.start()

    # get episodes and put them in the queue
    for episode in query_episodes():
        extension = episode.url.split(".")[-1]
        display_filename = episode.title + "." + extension
        filename = join(args.output, display_filename)
        if exists(filename):
            # already downloaded
            continue

        queue.put(
            WorkerQueueElement(
                episode=episode, filename=filename, display_filename=display_filename
            )
        )

    # wait until the queue gets empty
    try:
        queue.join()
    except KeyboardInterrupt:
        print("Finishing last download, then exiting")
    finish[0] = True  # stop worker threads
    # join threads
    for t in threads:
        t.join()
    finish_info[0] = True # stop the downloading info thread
    di_thread.join()
