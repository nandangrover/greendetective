import requests
import concurrent.futures
import time
import logging
from bs4 import BeautifulSoup
from datetime import timedelta
from django.utils import timezone
from urllib.parse import urljoin, urlparse, urlunparse
from detective.models import Staging, Company
import PyPDF2 as pypdf
import io
import re
from django.conf import settings
from rq import Queue
from tenacity import retry, stop_after_attempt, wait_exponential
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from ratelimit import limits, sleep_and_retry
import random
import os
import cloudscraper
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from random import choice
from functools import lru_cache


class Scraper:
    """
    Scraper class for scraping a domain
    """

    MAX_LINKS = int(os.getenv("MAX_LINKS", "30000"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "15000"))

    def __init__(self, company_id, start_url, urls_to_process=None):
        self.company = Company.objects.get(uuid=company_id)
        self.start_url = start_url
        self.domain = urlparse(start_url).netloc
        self.visited = set()
        self.to_visit = {start_url}
        self.urls_to_process = urls_to_process
        self.max_links = self.MAX_LINKS
        self.max_content_length = self.MAX_CONTENT_LENGTH
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.total_links_available = 0
        self.request_count = 0
        self.last_request_time = time.time()

        self.logger = logging.getLogger(__name__)
        self.redis = settings.REDIS_CONN
        self.scrape_queue = Queue("scraping", connection=self.redis)

        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            # Add more user agents here
        ]

        # Initialize cloudscraper
        self.scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}, delay=10
        )

        # Initialize undetected-chromedriver for JavaScript-heavy sites
        self.driver = None

        self.proxy_pool = []
        self.current_proxy_index = 0
        self._initialize_proxy_pool()

        self.proxy_cache = {}  # Cache for working proxies
        self.proxy_timeout = 5  # Timeout for proxy testing
        self.max_parallel_proxy_tests = 20  # Max parallel proxy tests
        self.proxy_refresh_interval = 300  # Refresh proxy list every 5 minutes
        self.last_proxy_refresh = 0

    def _initialize_proxy_pool(self):
        """Initialize a pool of proxies"""
        # Add your proxy list here
        proxy_list = [
            {"username": "user1", "password": "pass1", "host": "proxy1.com", "port": "8080"},
            {"username": "user2", "password": "pass2", "host": "proxy2.com", "port": "8080"},
            # Add more proxies
        ]

        self.proxy_pool = proxy_list

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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _scrape_content(self, url):
        try:
            proxy = self._get_proxy()
            response = self.scraper.get(url, proxies=proxy)
            soup = BeautifulSoup(response.content, "html.parser")
            texts = soup.stripped_strings
            content = " ".join(texts)
            content = self._clean_content(content)
            return self._split_and_return_content(url, content)
        except Exception as e:
            self.logger.error(f"Failed to scrape {url}: {e}")
            raise

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
            # Add verify=False to bypass SSL certificate verification
            response = requests.get(url, headers=self.headers, verify=False)

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

    def _scrape_js_content(self, url):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")

        driver = webdriver.Chrome(options=options)
        try:
            driver.get(url)
            content = driver.page_source
            soup = BeautifulSoup(content, "html.parser")
            return self._extract_content(soup)
        finally:
            driver.quit()

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

    def _get_driver(self):
        """Lazy initialization of the Chrome driver"""
        if self.driver is None:
            options = uc.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-blink-features=AutomationControlled")

            self.driver = uc.Chrome(options=options)
            # Set page load timeout
            self.driver.set_page_load_timeout(30)
        return self.driver

    def _make_request(self, url):
        """Try different methods to bypass Cloudflare"""
        methods = [self._try_cloudscraper, self._try_selenium, self._try_regular_request]

        for method in methods:
            try:
                response = method(url)
                if response and "Verifying your connection" not in response.text:
                    return response
                time.sleep(2)  # Wait between attempts
            except Exception as e:
                self.logger.warning(f"Method {method.__name__} failed for {url}: {e}")
                continue

        raise Exception("All bypass methods failed")

    def _try_cloudscraper(self, url):
        """Try using cloudscraper"""
        try:
            # First try without proxy
            response = self.scraper.get(url, timeout=30, allow_redirects=True)
            if response.status_code == 200:
                return response

            # If direct request fails, try with proxy
            proxies = self._get_proxy()
            if proxies:
                try:
                    return self.scraper.get(
                        url, timeout=30, allow_redirects=True, proxies=proxies
                    )
                except Exception as proxy_error:
                    self.logger.warning(f"Cloudscraper failed with proxy: {proxy_error}")
                    # Fall back to direct request
                    return self.scraper.get(url, timeout=30, allow_redirects=True)

            return response
        except Exception as e:
            self.logger.error(f"Cloudscraper failed: {e}")
            raise

    def _try_selenium(self, url):
        """Try using undetected-chromedriver"""
        try:
            # Initialize new driver instance for each request
            options = uc.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-blink-features=AutomationControlled")

            # Use fresh driver instance
            driver = uc.Chrome(options=options)
            driver.set_page_load_timeout(30)

            driver.get(url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            if "Verifying your connection" in driver.page_source:
                time.sleep(5)

            class SeleniumResponse:
                def __init__(self, driver):
                    self.text = driver.page_source
                    self.content = driver.page_source.encode("utf-8")
                    self.status_code = 200

            response = SeleniumResponse(driver)
            driver.quit()  # Clean up immediately
            return response
        except Exception as e:
            self.logger.error(f"Selenium request failed: {e}")
            if "driver" in locals():
                try:
                    driver.quit()
                except Exception:
                    pass
            raise

    def _try_regular_request(self, url):
        """Fallback to regular requests with additional headers"""
        headers = {
            "User-Agent": self._get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "DNT": "1",
        }

        session = requests.Session()
        return session.get(url, headers=headers, timeout=30, verify=False)

    def __del__(self):
        """Cleanup method"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                self.logger.error(f"Error while quitting driver: {e}")
                pass

    def _get_random_user_agent(self):
        return random.choice(self.user_agents)

    def _extract_links(self, content, base_url):
        """
        Extracts links from HTML content
        """
        try:
            soup = BeautifulSoup(content, "html.parser")

            # Check for security check page
            if soup.find(text=re.compile(r"Verifying your connection|Security check", re.I)):
                self.logger.warning(f"Security check page detected for {base_url}")
                return set()

            links = set()
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue

                # Handle relative URLs
                full_url = urljoin(base_url, href)

                # Only include URLs that are part of the base domain
                if self._is_same_domain(full_url):
                    links.add(full_url)

            if not links:
                self.logger.warning(f"No links found in content from {base_url}")

            return links
        except Exception as e:
            self.logger.error(f"Error extracting links from content: {e}")
            return set()

    def _is_same_domain(self, url):
        """
        Check if the URL belongs to the same domain as the start_url
        """
        try:
            parsed_url = urlparse(url)
            # Get base domain by removing www and splitting
            base_domain_parts = self.domain.replace("www.", "").split(".")
            url_domain_parts = parsed_url.netloc.replace("www.", "").split(".")

            # Compare the last two parts of the domain (e.g., 'zevero.com')
            return base_domain_parts[-2:] == url_domain_parts[-2:]
        except Exception as e:
            self.logger.error(f"Error checking domain for {url}: {e}")
            return False

    def _normalize_url(self, url):
        """Normalize URL by removing fragments, sorting query parameters, etc."""
        parsed = urlparse(url)
        # Remove fragment and normalize path
        normalized = parsed._replace(
            fragment="",
            path=parsed.path.rstrip("/"),
            query="&".join(sorted(parsed.query.split("&"))) if parsed.query else "",
        )
        return urlunparse(normalized)

    @lru_cache(maxsize=100)
    def _get_proxy(self):
        """Get a cached working proxy with parallel testing"""
        current_time = time.time()
        if current_time - self.last_proxy_refresh > self.proxy_refresh_interval:
            self._refresh_proxy_pool()
            self.last_proxy_refresh = current_time

        if self.proxy_cache:
            return choice(list(self.proxy_cache.items()))

        return None

    def _refresh_proxy_pool(self):
        """Refresh the proxy pool with parallel testing"""
        try:
            response = requests.get(
                "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
                timeout=10,
            )
            proxies = response.text.split("\n")[:100]  # Only take first 100 proxies

            # Test proxies in parallel
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_parallel_proxy_tests
            ) as executor:
                future_to_proxy = {
                    executor.submit(self._test_proxy, proxy.strip()): proxy.strip()
                    for proxy in proxies
                    if proxy.strip()
                }

                for future in concurrent.futures.as_completed(future_to_proxy):
                    proxy = future_to_proxy[future]
                    try:
                        if future.result():
                            self.proxy_cache[proxy] = time.time()
                    except Exception:
                        pass

            # Clean up old proxies
            current_time = time.time()
            self.proxy_cache = {
                proxy: timestamp
                for proxy, timestamp in self.proxy_cache.items()
                if current_time - timestamp < self.proxy_refresh_interval
            }

        except Exception as e:
            self.logger.error(f"Error refreshing proxy pool: {e}")

    def _test_proxy(self, proxy):
        """Optimized proxy testing"""
        try:
            test_url = self.start_url or "http://httpbin.org/ip"
            session = requests.Session()
            response = session.get(
                test_url,
                proxies={"http": f"http://{proxy}", "https": f"http://{proxy}"},
                timeout=self.proxy_timeout,
            )
            return response.status_code == 200
        except Exception:
            return False
