import threading
import weakref

import requests
from bs4 import BeautifulSoup
from cacherator import Cached, JSONCache
from logorator import Logger
import time


class Scraper(JSONCache):

    RETRIES = 4

    def __init__(self, url=""):
        self.url = url
        self.thread = threading.Thread(target=self._background_init, daemon=True)
        self.thread.start()
        self._response_code = None
        self._html = None
        weakref.finalize(self, self.join_thread)

    def __str__(self):
        return f"Scraper: ({self.response_code}) {self.url}"

    def _background_init(self):
        JSONCache.__init__(self, data_id=self.url, directory="data/scraper", logging=False)


    def join_thread(self):
        self.thread.join()

    @Logger()
    def fetch(self):
        for i in range(Scraper.RETRIES):
            self.fetch_attempt()
            if self._response_code < 400:
                Logger.note("HTML fetched successfully.", mode="short")
                break
            if i < Scraper.RETRIES - 1:
                Logger.note(f"HTML fetch failed - Response Code {self._response_code}. Waiting {2**i} seconds for next attempt.")
                time.sleep(2**i)
            else:
                Logger.note(f"HTML fetch failed - Response Code {self._response_code}. Giving up.")
        tmp = self.html
        tmp = self.response_code

    #@Logger()
    def fetch_attempt(self):
        rq = requests.get(self.url)
        self._response_code = rq.status_code
        self._html = rq.text

    def fetched_correctly(self):
        return self._response_code < 400

    @property
    @Cached()
    def html(self):
        return self._html

    @property
    @Cached()
    def response_code(self):
        return self._response_code

    @property
    @Cached()
    def soup(self):
        self.thread.join()
        return BeautifulSoup(self.html, "html.parser")

    @property
    def title(self):
        return self.soup.find("title").text


if __name__ == "__main__":
    s = Scraper(url="https://example.com/404")
    s.fetch()
    s.thread.join()
    print(s)
    #urls = [a.get("href") if a.get("href")[:4] == "http" else f"https://en.wikipedia.org{a.get('href')}" for a in s.soup.find_all("a")[:5]]
    #for u in urls[:5]:
    #    ns = Scraper(url=u)
    #    print(ns.title)
    # s.thread.join()
    # print(urls)
    # time.sleep(1)
