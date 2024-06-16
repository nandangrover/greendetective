from celery import shared_task
from detective.utils import Scrapper
import logging
import time

logger = logging.getLogger(__name__)


@shared_task
def refresh_graph_projection():
    logger.info("Refreshing graph projection")

    create_item_gds_graph()
    create_provider_gds_graph()

    logger.info("Refreshed graph projection")
