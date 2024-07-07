import logging
import time
from django.conf import settings
from detective.models import Run, Staging

logger = logging.getLogger(__name__)

POLLING_MAX_SECONDS = 300

def start_processing_run(staging_uuid, run_uuid):
    """
    Process run for a thread.
    """

    try:
        _start_polling(staging_uuid, run_uuid, 0)
    except Exception as e:
        _save_run_status(run_uuid, Run.STATUS_FAILED)
        _save_staging_status(staging_uuid, Staging.STATUS_FAILED)

        logger.error(f"Error while processing run for staging record: {staging_uuid}, run: {run_uuid}")
        
        logger.error(e)


def _start_polling(company_uuid, run_uuid, thread_uuid, elapsed_time=0):
    """
    Start polling for run status.
    """

    # Check if elapsed_time exceeds the timeout threshold
    if elapsed_time > POLLING_MAX_SECONDS:
        logger.error(f"Run processing timed out for thread: {thread_uuid}")

        # Save run as failed in db
        run_instance = Run.objects.get(run_uuid=run_uuid)
        _save_run_status(run_instance, Run.STATUS_FAILED)
        return

    logger.info(f"Processing run for thread: {thread_uuid}, elapsed_time: {elapsed_time}")

    run = Run.objects.get(run_uuid=run_uuid)
    # Retrieve thread and run information
    thread_oa_id = run.thread_oa_id
    run_oa_id = run.run_oa_id

    # Retrieve run information from openai
    conversation_object = Conversation(company_uuid)
    run = conversation_object.retrieve_run(thread_oa_id, run_oa_id)

    status = run.status
    if status in [Run.STATUS_IN_PROGRESS, Run.STATUS_QUEUED]:
        # Wait for 2 seconds and then start polling again
        time.sleep(settings.POLL_INTERVAL)
        elapsed_time += settings.POLL_INTERVAL

        steps = conversation_object.list_run_steps(thread_oa_id, run_oa_id)
        _process_run_steps(conversation_object, thread_oa_id, thread_uuid, run_uuid, steps)

        _start_polling(company_uuid, run_uuid, thread_uuid, elapsed_time)

    elif status == Run.STATUS_COMPLETED:
        run_instance = Run.objects.get(run_uuid=run_uuid)
        # Check for new message in thread
        steps = conversation_object.list_run_steps(thread_oa_id, run_oa_id)
        _process_run_steps(conversation_object, thread_oa_id, thread_uuid, run_uuid, steps)
        _save_run_status(run_instance, Run.STATUS_COMPLETED)

    elif status in [Run.STATUS_FAILED, Run.STATUS_CANCELLED, Run.STATUS_EXPIRED]:
        # Save run with appropriate status in db
        run_instance = Run.objects.get(run_uuid=run_uuid)
        _save_run_status(run_instance, status)

    else:
        # Save run as failed in db (default case)
        run_instance = Run.objects.get(run_uuid=run_uuid)
        _save_run_status(run_instance, Run.STATUS_FAILED)


def _save_run_status(run_uuid, status):
    run = Run.objects.get(run_uuid=run_uuid)
    run.status = status
    run.save()
    
def _save_staging_status(staging_uuid, status):
    staging = Staging.objects.get(staging_uuid=staging_uuid)
    staging.status = status
    staging.save()


def _save_statistic(message, message_type, content, thread_uuid, run_uuid, send_to_channel=True):
    """
    Save message in db.

    Args:
        message (Object): Message object
        message_type (str): Type of message
        content (str): Content of message
        thread_uuid (str): UUID of thread
        run_uuid (str): UUID of run

    Returns:
        None
    """
    
    message = Message.objects.create(
        conversation_thread_id=thread_uuid,
        run_id=run_uuid,
        message_oa_id=message.id,
        message=content,
        message_type=message_type,
        type=Message.TYPE_ASSISTANT,
    )
    
    if not message:
        raise Exception("Error while saving message in db")

    
    return message
