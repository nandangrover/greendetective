import logging
import os
from openai import OpenAI


class Completion:
    def __init__(self, message, rule, log_level=logging.INFO):
        """
        Initialize the Completion class.
        """

        self.message = message
        self.rule = rule
        self.model = "gpt-4o"

        open_ai_api_key = os.getenv("OPEN_AI_API_KEY", None)
        self.open_ai = OpenAI(api_key=open_ai_api_key)
        self.client = self.open_ai

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        self.logger.info("Initializing ChatBase...")

    def create_completion(self):
        """
        Create a completion.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self.rule,
                },
                {
                    "role": "user",
                    "content": self.message,
                },
            ],
        )

        return response.choices[0].message.content
