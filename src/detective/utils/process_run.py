import logging
import time
import json
from django.conf import settings
from detective.models import Run, Staging, RawStatistics
from detective.utils import Assistant

logger = logging.getLogger(__name__)

POLLING_MAX_SECONDS = 300
POLL_INTERVAL = 2


def start_processing_run(staging_uuid, run_uuid):
    """
    Process run for a thread.
    """

    try:
        _start_polling(staging_uuid, run_uuid, 0)
    except Exception as e:
        run = Run.objects.get(run_uuid=run_uuid)
        _save_run_status(run, Run.STATUS_FAILED)
        _save_staging_status(staging_uuid, Staging.STATUS_FAILED)

        logger.error(
            f"Error while processing run for staging record: {staging_uuid}, run: {run_uuid}"
        )

        logger.error(e)


def _start_polling(staging_uuid, run_uuid, elapsed_time=0):
    """
    Start polling for run status.
    """

    # Check if elapsed_time exceeds the timeout threshold
    if elapsed_time > POLLING_MAX_SECONDS:
        logger.error(f"Run processing timed out for run: {run_uuid}")

        # Save run as failed in db
        run_instance = Run.objects.get(run_uuid=run_uuid)
        _save_run_status(run_instance, Run.STATUS_FAILED)
        return

    run_instance = Run.objects.get(run_uuid=run_uuid)

    logger.info(
        f"Processing run for thread: {run_instance.thread_oa_id}, run: {run_instance.run_oa_id}"
    )

    # Retrieve thread and run information
    thread_oa_id = run_instance.thread_oa_id
    run_oa_id = run_instance.run_oa_id

    # Retrieve run information from openai
    assistant = Assistant(staging_uuid)
    run_openai = assistant.retrieve_run(thread_oa_id, run_oa_id)

    status = run_openai.status
    if status in [Run.STATUS_IN_PROGRESS, Run.STATUS_QUEUED]:
        # Wait for 2 seconds and then start polling again
        time.sleep(POLL_INTERVAL)
        elapsed_time += POLL_INTERVAL

        _start_polling(staging_uuid, run_uuid, elapsed_time)

    elif status == Run.STATUS_COMPLETED:
        # Check for new message in thread
        steps = assistant.list_run_steps(thread_oa_id, run_oa_id)
        _process_run_steps(assistant, thread_oa_id, staging_uuid, steps)
        _save_run_status(run_instance, Run.STATUS_COMPLETED)

    elif status in [Run.STATUS_FAILED, Run.STATUS_CANCELLED, Run.STATUS_EXPIRED]:
        # Save run with appropriate status in db
        _save_run_status(run_instance, status)

    else:
        # Save run as failed in db (default case)
        _save_run_status(run_instance, Run.STATUS_FAILED)


def _save_run_status(run, status):
    run.status = status
    run.save()


def _save_staging_status(staging_uuid, status):
    staging = Staging.objects.get(uuid=staging_uuid)
    staging.processed = status
    staging.save()


def _process_run_steps(assistant, thread_oa_id, staging_uuid, steps):
    logger.info(f"Processing run steps for thread: {thread_oa_id}")
    # Get message_oa_id of all steps
    message_oa_ids = []

    for step in steps:
        if step.step_details.type != "message_creation":
            continue
        message_id = step.step_details.message_creation.message_id
        message_oa_ids.append(message_id)

    # reverse the list to save the latest message last
    message_oa_ids.reverse()

    for message_oa_id in message_oa_ids:
        message = assistant.retrieve_message(thread_oa_id, message_oa_id)

        # Loop over content and save it in db
        for content in message.content:
            if content.type == "text":
                # convert text to dict
                content = content.text.value

                # print(content, "content yooo")

                json_content = json.loads(content)

                # if json_content is object, convert it to list

                if isinstance(json_content, dict):
                    if "claims" in json_content:
                        json_content = json_content["claims"]
                    elif "data" in json_content:
                        json_content = json_content["data"]
                    else:
                        json_content = [json_content]

                # if empty json_content, skip
                if not json_content:
                    continue

                _save_statistic(staging_uuid, json_content)


def _save_statistic(staging_uuid, content):
    """
    Save statistice in db.
    """
    staging = Staging.objects.get(uuid=staging_uuid)
    try:
        for obj in content:
            if "claim" not in obj or "evaluation" not in obj or "score" not in obj:
                logger.error(f"Invalid statistic object: {obj}")
                continue

            RawStatistics.objects.create(
                company=staging.company,
                staging=staging,
                claim=obj["claim"],
                evaluation=obj["evaluation"],
                score=obj["score"],
            )

        _save_staging_status(staging_uuid, Staging.STATUS_PROCESSED)
    except Exception as e:
        logger.error(f"Failed to save statistic: {e}")
