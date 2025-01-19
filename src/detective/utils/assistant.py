from openai import OpenAI
from tempfile import NamedTemporaryFile
import logging
import os
from django.db import transaction
from detective.models import Run, Staging, RawStatistics


class Assistant:
    ASSISTANT_TYPE_PRE = "pre"
    ASSISTANT_TYPE_POST = "post"

    def __init__(
        self,
        staging_uuid=None,
        stat_uuid=None,
        type=ASSISTANT_TYPE_PRE,
        log_level=logging.INFO,
    ):
        """
        Initialize the ChatBase class.
        """
        self.staging_data = Staging.objects.get(uuid=staging_uuid)
        self.stat_data = (
            RawStatistics.objects.get(uuid=stat_uuid) if stat_uuid else None
        )
        self.type = type

        open_ai_api_key = os.getenv("OPEN_AI_API_KEY", None)
        self.open_ai = OpenAI(api_key=open_ai_api_key)
        self.client = self.open_ai.beta
        self.assistant_id = (
            os.getenv("ASSISTANT_ID_PRE", None)
            if type == self.ASSISTANT_TYPE_PRE
            else os.getenv("ASSISTANT_ID_POST", None)
        )

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        self.logger.info("Initializing ChatBase...")

    def trigger_staging_run(self):
        """
        Trigger a run for a thread
        """
        try:
            with transaction.atomic():
                if self.staging_data.processed == Staging.STATUS_PROCESSED:
                    self.logger.info(
                        f"Staging data already processed: {self.staging_data.uuid}"
                    )
                    return

                url = self.staging_data.url
                knowledge = self.staging_data.raw
                company = self.staging_data.company
                # Create a thread
                messages = [
                    {
                        "role": "user",
                        "content": f"""This is the raw data for the url: {url}. Before processing any greenwashing claims, keep in mind what the company does.
                        
                        Company: {company.name}
                        Description: {company.about_summary}
                        
                        Raw data for processing: \n \n {knowledge}""",
                    }
                ]
                thread = self.create_thread(messages)

                self.create_run(thread.id)

                self.logger.info(f"Triggered run for thread: {thread.id}")

        except Exception as e:
            self.logger.error(e)
            raise e

    def trigger_statistic_run(self):
        """
        Trigger a run for a thread
        """
        # TODO: Need to attach file to the thread
        try:
            with transaction.atomic():
                if self.staging_data.processed != Staging.STATUS_PROCESSED:
                    self.logger.info(
                        f"Cant process statistic run for staging data: {self.staging_data.uuid}"
                    )
                    # Mark the statistic as processed
                    self.stat_data.processed = RawStatistics.STATUS_FAILED
                    self.stat_data.save()
                    return

                raw = self.staging_data.url
                claim = self.stat_data.claim
                evaluation = self.stat_data.evaluation
                # Create a thread
                messages = [
                    {
                        "role": "user",
                        "content": f"""
                        Claim: {claim}
                        
                        Evaluation: {evaluation}
                        
                        Raw data: \n \n {raw}
                        """,
                    }
                ]
                thread = self.create_thread(messages)

                self.create_run(thread.id)

                self.logger.info(
                    f"Triggered run for thread: {thread.id} for statistic: {self.stat_data.uuid}"
                )

        except Exception as e:
            self.logger.error(e)
            raise e

    def create_thread(self, messages):
        """
        Create a thread.
        """
        # TODO: Integrate file search
        return self.client.threads.create(
            messages=messages
        )

    def create_run(self, thread_id):
        from detective.utils import start_processing_run

        run = self.client.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant_id,
        )

        run_instance = Run.objects.create(
            run_oa_id=run.id,
            thread_oa_id=thread_id,
            staging=self.staging_data,
        )

        self.logger.info(f"Created run: {run.id}")

        (
            start_processing_run(self.staging_data.uuid, run_instance.run_uuid)
            if self.type == self.ASSISTANT_TYPE_PRE
            else None
        )
        (
            start_processing_run(
                self.staging_data.uuid,
                run_instance.run_uuid,
                self.stat_data.uuid,
                False,
            )
            if self.type == self.ASSISTANT_TYPE_POST
            else None
        )

        return run_instance

    def create_assistant_file(
        self,
        data,
        file_name=None,
    ):
        """
        Create an assistant file by attaching a
        [File](https://platform.openai.com/docs/api-reference/files) to an
        [assistant](https://platform.openai.com/docs/api-reference/assistants).
        """
        temp_json_file = NamedTemporaryFile(
            delete=True, suffix=".csv", prefix=file_name
        )
        data.to_csv(temp_json_file, sep="\t", index=False)
        file = self.open_ai.files.create(
            file=open(temp_json_file.name, "rb"), purpose="assistants"
        )

        return file.id

    def retrieve_thread(self, thread_id):
        """
        Retrieves a thread.
        """
        return self.client.threads.retrieve(thread_id=thread_id)

    def retrieve_run(self, thread_id, run_id):
        """
        Retrieves a run.
        """
        return self.client.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run_id,
        )

    def list_run_steps(
        self,
        thread_id,
        run_id,
    ):
        """
        List steps in a run.
        """
        return self.client.threads.runs.steps.list(thread_id=thread_id, run_id=run_id)

    def retrieve_message(
        self,
        thread_id,
        message_id,
    ):
        """
        Retrieves a message.
        """
        return self.client.threads.messages.retrieve(
            thread_id=thread_id, message_id=message_id
        )
