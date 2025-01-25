import time
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def retry_on_transaction_failure(max_retries=3, backoff_factor=0.5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:  # Last attempt
                        logger.error(f"Final retry attempt failed: {str(e)}")
                        raise
                    wait_time = backoff_factor * (2**attempt)  # Exponential backoff
                    logger.warning(
                        f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {str(e)}"
                    )
                    time.sleep(wait_time)
            return None

        return wrapper

    return decorator
