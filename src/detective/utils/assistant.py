from openai import OpenAI
import logging
import os
from django.db import transaction
from detective.models import Run, Staging


class Assistant:
    def __init__(self, staging_uuid=None, log_level=logging.INFO):
        """
        Initialize the ChatBase class.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        self.logger.info("Initializing ChatBase...")

        open_ai_api_key = os.getenv("OPEN_AI_API_KEY", None)

        self.staging_data = Staging.objects.get(uuid=staging_uuid)

        self.open_ai = OpenAI(api_key=open_ai_api_key)
        self.client = self.open_ai.beta
        self.assistant_id = os.getenv("ASSISTANT_ID", None)

    def trigger_run(self):
        """
        Trigger a run for a thread
        """
        try:
            with transaction.atomic():
                if self.staging_data.processed == Staging.STATUS_PROCESSED:
                    self.logger.info(f"Staging data already processed: {self.staging_data.uuid}")
                    return
                
                url = self.staging_data.url
                knowledge = self.staging_data.raw_html
                # Create a thread
                messages = [
                    {
                        "role": "user",
                        "content": f"This is the raw data for the url: {url}. Return data in appropriate JSON structure: \n \n {knowledge}",
                    }
                ]
                thread = self.create_thread(messages)

                self.create_run(thread.id)

                self.logger.info(f"Triggered run for thread: {thread.id}")

        except Exception as e:
            self.logger.error(e)
            raise e

    def create_thread(self, messages):
        """
        Create a thread.
        """
        return self.client.threads.create(
            messages=messages,
        )

    def create_run(self, thread_id):
        from detective.tasks import process_run

        run = self.client.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant_id,
        )

        run_instance = Run.objects.create(
            run_oa_id=run.id,
            thread_oa_id=thread_id,
            staging=self.staging_data,
        )

        process_run.delay(self.staging_data.uuid, run_instance.run_uuid)

        return run_instance

    def retrieve_thread(self, thread_id):
        """
        Retrieves a thread.
        """
        return self.client.threads.retrieve(thread_id=thread_id)

    def retrieve_run(
        self,
        thread_id,
        run_id
    ):
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
        return self.client.threads.runs.steps.list(
            thread_id=thread_id,
            run_id=run_id
        )
        
    def retrieve_message(
        self,
        thread_id,
        message_id,
    ):
        """
        Retrieves a message.
        """
        return self.client.threads.messages.retrieve(
            thread_id=thread_id,
            message_id=message_id
        )