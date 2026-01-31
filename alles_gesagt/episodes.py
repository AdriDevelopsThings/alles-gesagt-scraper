from dataclasses import dataclass
from typing import Generator, Optional

import requests
from bs4 import BeautifulSoup

URL = "https://www.zeit.de/serie/alles-gesagt"


@dataclass
class Episode:
    title: str
    url: str


def __query(url: str) -> Optional[str]:
    """Query the response text of an url."""
    response = requests.get(url)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.text


def __query_bs4(url: str) -> Optional[BeautifulSoup]:
    """Query the response text interpreted as a BeautifulSoup object (HTML parser)"""
    text = __query(url)
    if not text:
        return None
    return BeautifulSoup(text, features="html.parser")


def query_episodes() -> Generator[Episode]:
    page = 1
    while True:
        bs4 = __query_bs4(URL + f"?p={page}")
        if not bs4:
            break
        containers = bs4.find_all(class_="zon-teaser__container")
        for container in containers:
            title = container.find(class_="zon-teaser__title").text
            audio = container.find("audio")
            if not title or not audio:
                continue
            url = audio.attrs["data-src-adfree"]
            if not url:
                url = audio.attrs["src"]
            yield Episode(title=title, url=url)
        page += 1
