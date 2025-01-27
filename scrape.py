from argparse import ArgumentParser
from bs4 import BeautifulSoup
from os.path import join, exists
from os import mkdir
import requests
from threading import Thread, Lock
from queue import Queue, Empty
from time import sleep

URL = "https://www.zeit.de/serie/alles-gesagt"
WORKER_COUNT = 8

parser = ArgumentParser()
parser.add_argument("-o", "--output", default="episodes", help="Destination where episodes should be saved")

"""Query the response text of a url."""
def __query(url: str) -> str:
    response = requests.get(url)
    response.raise_for_status()
    return response.text

"""Query the response text interpreted as a BeautifulSoup object (HTML parser)"""
def __query_bs4(url: str) -> BeautifulSoup:
    text = __query(url)
    return BeautifulSoup(text, features="html.parser")

"""Create a generator that yields episodes objects.
Yields: Dict that contains a "title" and an "url" key.
"""
def query_episodes():
    url = URL
    while True:
        bs4 = __query_bs4(url)
        containers: list[BeautifulSoup] = bs4.find_all(class_="zon-teaser__container")
        for container in containers:
            title = container.find(class_="zon-teaser__title").text
            audio = container.find("audio")
            if not title or not audio:
                continue
            url = audio.attrs["data-src-adfree"]
            if not url:
                url = audio.attrs["src"]
            yield {
                "title": title,
                "url": url
            }
        
        current_page = bs4.find("li", class_="pager__page--current")
        next_page_li = current_page.find_next("li", class_="pager__page")
        if not next_page_li:
            break
        url = next_page_li.find("a").attrs["href"]

"""Download worker
This worker gets an element from the queue, download this element and puts
download information in the `currently_downloading` dict. The function of the lock
is to prevent that two threads doing weird things at `currently_downloading` at the same time.
"""
def worker(queue: Queue, currently_downloading: dict, lock: Lock, finish: list[bool]):
    while not finish[0]:
        try:
            i = queue.get(timeout=1)
        except Empty:
            continue
        lock.acquire()
        # 0% downloaded at start
        currently_downloading[i["display_filename"]] = 0
        lock.release()
        response = requests.get(i["url"], stream=True)
        response.raise_for_status()
        length = int(response.headers["content-length"])
        written = 0
        with open(i["filename"], "wb") as file:
            # split content in 64 KB chunks
            for chunk in response.iter_content(1024 * 64):
                file.write(chunk)
                written += len(chunk)
                percent = round((written / length) * 100)
                lock.acquire()
                currently_downloading[i["display_filename"]] = percent
                lock.release()
        # download is finished
        lock.acquire()
        del currently_downloading[i["display_filename"]]
        lock.release()
        queue.task_done()


"""Download info thread
This thread function prints information about the files that are currently downloaded. The lock is 
assigned to the `currently_downloading` dict. The `finish` list consists of exact one bool item.
The thread stops working the this finish item becomes True. Otherwise it will print information
every 100ms.
"""
def downloading_info_thread(currently_downloading: dict, lock: Lock, finish: list[bool]):
    s = ""
    while not finish[0]:
        # first of all we have to put our cursor back to the start of the last string
        old_lines = s.count("\n")
        if old_lines:
            print(f"\033[{old_lines}F", end="", flush=True)
        s = "" # we start with an empty string
        # now we can construct this string
        lock.acquire()
        for filename, p in currently_downloading.items():
            s += f"Downloading {filename}... {p}%\033[K\n" # the line should end before the \n, so we use this ansi code here
        if len(currently_downloading) != 0: # we can print the new information
            # but if we can't replace all old lines with new ones, because we have less lines generated than before
            # we have to clear the other lines
            new_lines = s.count("\n")
            if new_lines < old_lines:
                s += "\033[K\n" * (old_lines - new_lines)
            print(s, end="", flush=True)
        lock.release()
        sleep(0.1)

def main():
    args = parser.parse_args()
    # create the output directory if it does not exist
    if not exists(args.output):
        mkdir(args.output)
    
    # create thread variables
    currently_downloading_lock = Lock()
    currently_downloading = {}
    queue = Queue()
    finish = [False]

    # construct threads and start them
    threads = []
    for i in range(WORKER_COUNT):
        thread = Thread(target=worker, args=(queue, currently_downloading, currently_downloading_lock, finish))
        thread.start()
        threads.append(thread)
    di_thread = Thread(target=downloading_info_thread, args=(currently_downloading, currently_downloading_lock, finish))
    di_thread.start()
    
    # get episodes and put them in the queue
    for episode in query_episodes():
        extension = episode["url"].split(".")[-1]
        display_filename = episode["title"] + "." + extension
        filename = join(args.output, display_filename)
        if exists(filename):
            # already downloaded
            continue
        queue.put({
            "url": episode["url"],
            "filename": filename,
            "display_filename": display_filename # display filename is without relative path
        })
    # wait until the queue gets empty
    queue.join()
    finish[0] = True # stop the downloading info thread
    # join threads
    for t in threads:
        t.join()
    di_thread.join()

if __name__ == "__main__":
    main()