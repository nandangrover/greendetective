# scraper.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import concurrent.futures
import time
from .models import CompanyStaging
from django.utils import timezone
import uuid

class Scraper:
    def __init__(self, start_url, company_uuid):
        self.start_url = start_url
        self.company_uuid = company_uuid
        self.domain = urlparse(start_url).netloc
        self.visited = set()
        self.to_visit = {start_url}
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def get_all_links(self, url):
        try:
            response = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            links = set()

            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.startswith('/'):
                    href = urljoin(url, href)
                if self.domain in href and href not in links:
                    links.add(href)
            
            return links
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            return set()

    def scrape_content(self, url):
        try:
            response = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(response.content, 'html.parser')
            texts = soup.stripped_strings
            content = ' '.join(texts)
            return content
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            return ''

    def save_to_staging(self, url, raw_html):
        try:
            staging_entry = CompanyStaging.objects.create(
                uuid=uuid.uuid4(),
                company_uuid=self.company_uuid,
                url=url,
                raw_html=raw_html,
            )
            print(f"Saved to staging: {url}")
        except Exception as e:
            print(f"Failed to save to staging: {e}")

    def crawl_domain_and_save(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            while self.to_visit:
                futures = []
                for url in list(self.to_visit):
                    if url not in self.visited:
                        self.visited.add(url)
                        print(f"Visiting: {url}")
                        futures.append(executor.submit(self.get_all_links, url))
                        self.to_visit.remove(url)
                
                for future in concurrent.futures.as_completed(futures):
                    links = future.result()
                    new_links = links - self.visited
                    self.to_visit.update(new_links)

                content_futures = [executor.submit(self.scrape_content, url) for url in self.visited if url not in self.visited]
                for content_future in concurrent.futures.as_completed(content_futures):
                    content = content_future.result()
                    if content:
                        self.save_to_staging(url, content)
                
                # Respectful crawling: sleep for a while to avoid detection
                time.sleep(1)
