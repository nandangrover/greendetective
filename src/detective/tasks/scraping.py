from celery import shared_task, group
from django.conf import settings
from detective.utils import Scraper
from detective.models import Staging
import logging
import time
import requests
import random

logger = logging.getLogger(__name__)


@shared_task(queue=settings.CELERY_QUEUE_SCRAPE, rate_limit=settings.CELERY_RATE_LIMIT_SCRAPE)
def scrape_single_url(
    company_id: int, url: str, total_urls: int = None, current_index: int = None
) -> None:
    """
    Scrapes a single URL and saves the content to staging
    """
    try:
        # Create scraper instance to check domain
        scraper = Scraper(company_id, url)

        # Check if URL belongs to the same domain
        if not scraper._is_same_domain(url):
            logger.info(f"Skipping URL {url} as it's not part of the base domain")
            return

        logger.info(f"Scraping {url}")

        # Check if the URL is already in the database
        if Staging.objects.filter(url=url).exists():
            logger.info(f"URL {url} already exists in the database")
            return

        start_time = time.time()
        results = scraper._scrape_content(url)

        for url, content in results:
            if content:
                scraper._save_to_staging(url, content)

        # Log ETA if we have progress information
        if total_urls is not None and current_index is not None:
            elapsed_time = time.time() - start_time
            avg_time_per_url = elapsed_time  # Since this is a single URL
            remaining_urls = total_urls - current_index
            eta_seconds = remaining_urls * avg_time_per_url
            eta_str = time.strftime("%H:%M:%S", time.gmtime(eta_seconds))

            logger.info(f"Scraped {current_index}/{total_urls} - ETA: {eta_str} - URL: {url}")

    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")


@shared_task(queue=settings.CELERY_QUEUE_SCRAPE, rate_limit=settings.CELERY_RATE_LIMIT_SCRAPE)
def process_link_batch(company_id: int, links: list) -> None:
    """
    Processes a batch of links by scraping their content
    """
    for link in links:
        scrape_single_url.delay(company_id, link)


@shared_task(queue=settings.CELERY_QUEUE_SCRAPE, rate_limit=settings.CELERY_RATE_LIMIT_SCRAPE)
def crawl_domain(company_id: int, start_url: str) -> None:
    """
    Main task to crawl a domain. Returns list of all tasks created.
    """
    scraper = Scraper(company_id, start_url)
    visited = set()
    to_visit = {start_url}
    total_links_extracted = 0
    all_scraping_tasks = []

    while to_visit and total_links_extracted < Scraper.MAX_LINKS:
        # Calculate progress
        progress = (total_links_extracted / Scraper.MAX_LINKS) * 100
        remaining = Scraper.MAX_LINKS - total_links_extracted
        logger.info(
            f"Progress: {progress:.1f}% - Scraped: {total_links_extracted}, Remaining: {remaining}"
        )

        # Collect links from current batch of URLs
        current_batch_tasks = []
        for i, url in enumerate(to_visit):
            # Ensure URL is not already in visited
            if url not in visited:
                current_batch_tasks.append(
                    scrape_single_url.s(
                        company_id,
                        url,
                        total_urls=Scraper.MAX_LINKS,
                        current_index=total_links_extracted + i,
                    )
                )

        # Add current batch tasks to overall task list
        all_scraping_tasks.extend(current_batch_tasks)

        # Execute current batch and get new links
        group(current_batch_tasks).apply_async()
        new_links = set()

        for url in to_visit:
            try:
                # Add delay between requests
                time.sleep(random.uniform(2, 5))  # Increased delay

                response = scraper._make_request(url)
                if response.status_code == 200:
                    # Extract links from the response
                    extracted_links = scraper._extract_links(response.content, url)
                    if not extracted_links:
                        logger.warning(f"No links extracted from {url}")
                    normalized_links = {scraper._normalize_url(link) for link in extracted_links}
                    new_links.update(normalized_links)
                else:
                    logger.warning(f"Got status code {response.status_code} for {url}")
            except Exception as e:
                logger.error(f"Error getting links from {url}: {e}")
                continue

        visited.update(to_visit)
        # Remove already visited URLs and ensure uniqueness
        new_links = new_links - visited

        if total_links_extracted + len(new_links) > Scraper.MAX_LINKS:
            new_links = set(list(new_links)[: Scraper.MAX_LINKS - total_links_extracted])

        to_visit = new_links
        total_links_extracted += len(new_links)
        logger.info(
            f"Visited: {len(visited)}, To visit: {len(to_visit)}, Total links extracted: {total_links_extracted}"
        )

    # Return all tasks that were created
    return all_scraping_tasks
