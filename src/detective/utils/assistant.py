from openai import OpenAI
import logging
import os
from django.db import transaction
from detective.models import Run, Staging
from detective.tasks import process_run

class Assistant:
    def __init__(self, staging_uuid=None, log_level=logging.INFO):
        """
        Initialize the ChatBase class.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        self.logger.info("Initializing ChatBase...")

        open_ai_api_key = os.getenv("OPEN_AI_API_KEY", None)

        self.staging_data = Staging.objects.get(staging_uuid=staging_uuid)

        self.open_ai = OpenAI(api_key=open_ai_api_key)
        self.client = self.open_ai.beta
        self.assistant_id = os.getenv("ASSISTANT_ID", None)
        self.logger.info(
            "Assistant initialized for company: {}".format(self.company_uuid)
        )

    def trigger_run(self):
        """
        Trigger a run for a thread
        """
        try:
            with transaction.atomic():
                url = self.staging_data.url
                knowledge = self.staging_data.knowledge
                # Create a thread
                messages = [
                    {
                        "role": "user",
                        "content": f"This is the raw data for the url: {url}. \n \n {knowledge}",
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
        
        run =  self.client.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant_id,
        )
        
        run_instance = Run.objects.create(
            run_oa_id=run.id,
            thread_oa_id=thread_id,
            staging_uuid=self.staging_data.staging_uuid,
        )
        
        process_run.delay(self.staging_data.staging_uuid, run_instance.run_uuid)
        
        return run_instance

    def retrieve_thread(self, thread_id):
        """
        Retrieves a thread.
        """
        return self.client.threads.retrieve(thread_id=thread_id)
