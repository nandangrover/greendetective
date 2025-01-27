import json
import logging
from detective.utils.run.base import BaseRunProcessor
from detective.models import RawStatistics

logger = logging.getLogger(__name__)


class PostRunProcessor(BaseRunProcessor):
    def _process_run_steps(self, assistant, thread_oa_id, steps):
        logger.info(
            f"Processing run steps for thread: {thread_oa_id} - stat_uuid: {self.stat_uuid}"
        )

        message_oa_ids = []
        for step in steps:
            if step.step_details.type == "message_creation":
                message_id = step.step_details.message_creation.message_id
                message_oa_ids.append(message_id)

        message_oa_ids.reverse()

        for message_oa_id in message_oa_ids:
            message = assistant.retrieve_message(thread_oa_id, message_oa_id)
            for content in message.content:
                if content.type == "text":
                    try:
                        json_content = json.loads(content.text.value)
                        if isinstance(json_content, dict):
                            raw_statistic = RawStatistics.objects.get(uuid=self.stat_uuid)
                            raw_statistic.comparison_analysis = json_content

                            if "defunct" in json_content and json_content["defunct"]:
                                raw_statistic.defunct = True
                                logger.info(
                                    f"Marked claim as defunct based on comparison analysis: {self.stat_uuid}"
                                )
                            else:
                                raw_statistic.defunct = False
                                logger.info(f"Claim marked as not defunct: {self.stat_uuid}")

                            raw_statistic.save()
                            logger.info(
                                f"Stored comparison analysis for statistic: {self.stat_uuid}"
                            )

                    except json.JSONDecodeError as e:
                        logger.error(f"JSON parsing error: {e}")
                        logger.error(f"Raw content: {content.text.value}")
                    except Exception as e:
                        logger.error(f"Error processing content: {e}")
                        logger.error(f"Raw content: {content.text.value}")

        self._save_statistic_status(self.stat_uuid, RawStatistics.STATUS_PROCESSED)

    def _handle_failure(self):
        self._save_statistic_status(self.stat_uuid, RawStatistics.STATUS_FAILED)
