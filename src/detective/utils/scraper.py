import requests
import concurrent.futures
import time
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from detective.models import Staging
from detective.models import Company


# TODO: Should be able to process pds, images as well
class Scraper:
    def __init__(self, company_id, start_url, urls_to_process=None):
        self.company = Company.objects.get(uuid=company_id)
        self.start_url = start_url
        self.domain = urlparse(start_url).netloc
        self.visited = set()
        self.to_visit = {start_url}
        self.urls_to_process = urls_to_process
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        self.logger = logging.getLogger(__name__)

    def get_all_links(self, url):
        try:
            response = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(response.content, "html.parser")
            links = set()

            # TODO: Also get google link for company name and greenwashing and top 10 results
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if href.startswith("/"):
                    href = urljoin(url, href)
                if self.domain in href and href not in links:
                    links.add(href)

            return links
        except requests.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            return set()

    def scrape_content(self, url):
        try:
            response = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(response.content, "html.parser")
            texts = soup.stripped_strings
            content = " ".join(texts)
            return url, content
        except requests.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            return ""

    def save_to_staging(self, url, raw_html):
        try:
            Staging.objects.create(
                company_id=self.company,
                url=url,
                raw_html=raw_html,
            )
            self.logger.info(f"Saved to staging: {url}")
        except Exception as e:
            self.logger.error(f"Failed to save to staging: {e}")

    def crawl_domain_and_save(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            if self.urls_to_process:
                # urls_to_process is array of urls to process, so we don't need to crawl the domain
                for future in [
                    executor.submit(self.scrape_content, url)
                    for url in self.urls_to_process
                ]:
                    url, content = future.result()
                    if content:
                        self.save_to_staging(url, content)

                    time.sleep(1)
            else:
                while len(self.to_visit) > 0:
                    new_links = set()
                    for future in [
                        executor.submit(self.get_all_links, url)
                        for url in self.to_visit
                    ]:
                        new_links.update(future.result())
                    self.visited.update(self.to_visit)
                    self.to_visit = new_links - self.visited
                    self.logger.info(
                        f"Visited: {len(self.visited)}, To visit: {len(self.to_visit)}"
                    )
                    time.sleep(1)

                for future in [
                    executor.submit(self.scrape_content, url) for url in self.visited
                ]:
                    url, content = future.result()
                    if content:
                        self.save_to_staging(url, content)

                    time.sleep(1)
