import requests
import concurrent.futures
import time
import logging
from bs4 import BeautifulSoup
from datetime import timedelta, timezone
from urllib.parse import urljoin, urlparse
from detective.models import Staging, Company
import PyPDF2 as pypdf
import io
import re


class Scraper:
    def __init__(self, company_id, start_url, urls_to_process=None):
        self.company = Company.objects.get(uuid=company_id)
        self.start_url = start_url
        self.domain = urlparse(start_url).netloc
        self.visited = set()
        self.to_visit = {start_url}
        self.urls_to_process = urls_to_process
        self.max_links = 500
        self.max_content_length = 15000  # Max characters per content part
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.total_links_available = 0

        self.logger = logging.getLogger(__name__)

    def scrape_about_section(self):
        try:
            default_about_url = (
                self.domain + "/about" if not self.domain.endswith("/") else self.domain + "about"
            )
            about_url = (
                default_about_url if not self.company.about_url else self.company.about_url
            )

            # Add http if not present
            if not about_url.startswith("http"):
                about_url = "https://" + about_url

            response = requests.get(about_url, headers=self.headers)
            soup = BeautifulSoup(response.content, "html.parser")
            texts = soup.stripped_strings
            content = " ".join(texts)
            content = self._clean_content(content)
            return content
        except requests.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            return ""

    def crawl_domain_and_save(self):
        total_links_extracted = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            if self.urls_to_process:
                futures = [
                    executor.submit(self._scrape_content, url) for url in self.urls_to_process
                ]
                for future in concurrent.futures.as_completed(futures):
                    results = future.result()
                    for url, content in results:
                        if content:
                            self._save_to_staging(url, content)
                    time.sleep(1)
            else:
                while self.to_visit and total_links_extracted < self.max_links:
                    new_links = set()
                    futures = [executor.submit(self.get_all_links, url) for url in self.to_visit]
                    for future in concurrent.futures.as_completed(futures):
                        links = future.result()
                        self.total_links_available += len(links)
                        new_links.update(links)

                    self.visited.update(self.to_visit)
                    new_links = new_links - self.visited

                    if total_links_extracted + len(new_links) > self.max_links:
                        new_links = set(list(new_links)[: self.max_links - total_links_extracted])

                    self.to_visit = new_links
                    total_links_extracted += len(new_links)
                    self.logger.info(
                        f"Visited: {len(self.visited)}, To visit: {len(self.to_visit)}, Total links extracted: {total_links_extracted}, Total links available: {self.total_links_available}"
                    )

                    time.sleep(1)

                futures = [
                    executor.submit(self._scrape_content, url)
                    for url in list(self.visited)[: self.max_links]
                ]
                for future in concurrent.futures.as_completed(futures):
                    results = future.result()
                    for url, content in results:
                        if content:
                            self._save_to_staging(url, content)
                    time.sleep(1)

    def _clean_content(self, raw_text):
        if raw_text is None or raw_text.strip() == "":
            return "No content found"

        text_content = str(raw_text)
        text_content = (
            text_content.replace("�", " ")
            .replace("\n", " ")
            .replace("\t", " ")
            .replace("\r", " ")
            .replace("|", " ")
            .replace("\x00", "")  # Remove NUL characters
        )
        text_content = re.sub(r"\[[0-9]*\]", " ", text_content)
        text_content = re.sub(r"\s+", " ", text_content)
        text_content = re.sub(r"[\xc2\x99\x82\x92]", "", text_content)

        text_content = re.sub('(?<=[?.!"])\s+(?=[?.!"])', "", text_content)
        text_content = re.sub(r'\s+([?.!"])', r"\1", text_content)
        text_content = re.sub(r'([?.!"])+\s', r"\1", text_content)
        text_content = re.sub(r"\.+", ". ", text_content)
        text_content = (
            text_content.replace("?.", "?")
            .replace("!.", "!")
            .replace(":.", ":")
            .replace("-.", "-")
        )
        text_content = text_content.strip()
        return text_content

    def _pdf_contains_images(self, pdf_io_bytes):
        reader = pypdf.PdfReader(pdf_io_bytes, strict=True)
        if len(reader.pages) <= 2:
            for i in range(len(reader.pages)):
                page = reader.pages[i]
                if "/XObject" in page["/Resources"]:
                    xObject = page["/Resources"]["/XObject"].get_object()
                    for obj in xObject:
                        if xObject[obj]["/Subtype"] == "/Image":
                            error_name = (
                                "PDF is less than or equal to 2 pages and contains images"
                            )
                            self.logger.warning(error_name)
                            return True
        else:
            self.logger.info("PDF has more than 2 pages")
        return False

    def get_all_links(self, url):
        try:
            response = requests.get(url, headers=self.headers)
            content_type = response.headers.get("Content-Type", "")

            links = set()

            if "text/html" in content_type:
                soup = BeautifulSoup(response.content, "html.parser")
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    if href.startswith("/"):
                        href = urljoin(url, href)
                    if self.domain in href and href not in self.visited and "careers" not in href:
                        links.add(href)
            elif "application/pdf" in content_type or url.endswith(".pdf"):
                links.add(url)
            else:
                self.logger.warning(f"Skipping non-HTML and non-PDF content at {url}")
                return set()

            return links
        except requests.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            return set()
        except Exception as e:
            self.logger.error(f"Failed to parse links from {url}: {e}")
            return set()

    def _scrape_content(self, url):
        url_exists = Staging.objects.filter(
            url=url, created_at__gte=timezone.now() - timedelta(days=30)
        ).exists()

        if url_exists:
            self.logger.info(f"Skipping {url} as it was scraped less than 1 month ago")
            return [(url, "")]

        if url.endswith(".pdf"):
            return self._scrape_pdf_content(url)
        else:
            return self._scrape_html_content(url)

    def _scrape_html_content(self, url):
        try:
            response = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(response.content, "html.parser")
            texts = soup.stripped_strings
            content = " ".join(texts)
            content = self._clean_content(content)
            return self._split_and_return_content(url, content)
        except requests.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            return [(url, "")]
        except Exception as e:
            self.logger.error(f"Failed to parse HTML content from {url}: {e}")
            return [(url, "")]

    def _scrape_pdf_content(self, url):
        try:
            response = requests.get(url, headers=self.headers)

            # Check if the content type is actually a PDF
            content_type = response.headers.get("Content-Type", "")
            if "application/pdf" not in content_type:
                self.logger.error(f"Content at {url} is not a PDF. Skipping.")
                return [(url, "")]

            pdf_io_bytes = io.BytesIO(response.content)

            if self._pdf_contains_images(pdf_io_bytes):
                self.logger.warning(
                    f"PDF at {url} contains images and has 2 or fewer pages. Skipping."
                )
                return [(url, "")]

            text_list = []
            pdf = pypdf.PdfReader(pdf_io_bytes)

            num_pages = len(pdf.pages)

            if num_pages > 100:
                self.logger.info(f"Skipping PDF with more than 100 pages: {url}")
                return [(url, "")]

            for page in range(num_pages):
                page_text = pdf.pages[page].extract_text()
                page_text = page_text.replace("\x00", "")  # Remove NUL characters
                text_list.append(page_text)

            text = "\n".join(text_list)
            text = self._clean_content(text)
            return self._split_and_return_content(url, text)
        except requests.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            return [(url, "")]
        except Exception as e:
            self.logger.error(f"Failed to extract PDF content from {url}: {e}")
            return [(url, "")]

    def _split_and_return_content(self, url, text):
        if len(text) <= self.max_content_length:
            return [(url, text)]
        parts = []
        for i in range(0, len(text), self.max_content_length):
            part = text[i : i + self.max_content_length]
            parts.append((url, part))
        return parts

    def _save_to_staging(self, url, raw_html):
        try:
            Staging.objects.create(
                company=self.company,
                url=url,
                raw=raw_html,
            )
            self.logger.info(f"Saved to staging: {url}")
        except Exception as e:
            self.logger.error(f"Failed to save to staging: {e}")
