import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from detective.models import SustainabilityGlossary
from detective.utils.completion import Completion
import re
import json

SOURCES = [
    {
        "url": "https://www.british-business-bank.co.uk/business-guidance/guidance-articles/sustainability/glossary-of-terms#230548828-2411136191",
        "category": "Business Sustainability",
        "chunk_size": 10000,
        "defunct": True,
    },
    {
        "url": "https://www.vision2025.org.uk/glossary-of-sustainability-terms/",
        "category": "General Sustainability",
        "chunk_size": 10000,
        "defunct": True,
    },
    {
        "url": "https://www.ucem.ac.uk/sustainability-glossary/",
        "category": "Academic Sustainability",
        "chunk_size": 10000,
        "defunct": True,
    },
    {
        "url": "https://brainboxai.com/en/resources/sustainability-glossary",
        "category": "AI Sustainability",
        "chunk_size": 10000,
        "defunct": True,
    },
]

EXTRACTION_PROMPT = """
You are an expert in sustainability terminology. Extract glossary terms and their definitions from the provided HTML content.

Return the results in JSON format with the following structure:
{
    "terms": [
        {
            "term": "Term name",
            "definition": "Detailed definition",
            "context": "Additional context if available"
        }
    ]
}

Guidelines:
1. Extract all relevant sustainability terms and their definitions
2. Include only complete term-definition pairs
3. Preserve the original meaning and context
4. Remove any HTML tags or formatting
5. If a term has multiple definitions, create separate entries
6. Include any relevant context that helps explain the term

HTML Content:
{content}
"""


def split_content(content, chunk_size):
    """Split content into chunks of specified size"""
    return [content[i : i + chunk_size] for i in range(0, len(content), chunk_size)]


class Command(BaseCommand):
    help = "Load sustainability glossary terms from various sources using AI extraction"

    def handle(self, *args, **options):
        self.stdout.write("Loading sustainability glossary terms using AI extraction...")

        for source in SOURCES:
            if source["defunct"]:
                self.stdout.write(f'Skipping defunct source: {source["url"]}')
                continue

            self.stdout.write(f'Processing source: {source["url"]}')
            try:
                # Fetch and parse HTML content
                response = requests.get(source["url"])
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")

                # Remove unnecessary elements
                for element in soup(["script", "style", "nav", "footer"]):
                    element.decompose()

                # Get clean HTML content
                content = str(soup.body) if soup.body else str(soup)

                # Split content into chunks if needed
                chunk_size = source.get("chunk_size", None)
                if chunk_size and len(content) > chunk_size:
                    chunks = split_content(content, chunk_size)
                    self.stdout.write(f"Splitting content into {len(chunks)} chunks...")
                else:
                    chunks = [content]

                all_terms = []

                # Process each chunk
                for i, chunk in enumerate(chunks):
                    self.stdout.write(f"Processing chunk {i+1} of {len(chunks)}...")

                    # Use AI to extract terms and definitions
                    completion = Completion(message=chunk, rule=EXTRACTION_PROMPT)
                    result = completion.create_completion()

                    try:
                        # Clean the response if it starts with ```json
                        if result.startswith("```json"):
                            result = result[7:]  # Remove ```json
                        if result.endswith("```"):
                            result = result[:-3]  # Remove trailing ```

                        # Try to parse the response as JSON
                        response_data = json.loads(result.strip())
                        if not isinstance(response_data, dict) or "terms" not in response_data:
                            raise ValueError("Invalid response format: missing 'terms' key")

                        terms_data = response_data["terms"]
                        if not isinstance(terms_data, list):
                            raise ValueError("Invalid response format: 'terms' should be a list")

                        all_terms.extend(terms_data)
                    except json.JSONDecodeError as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Invalid JSON in AI response for chunk {i+1}: {str(e)}"
                            )
                        )
                        self.stdout.write(self.style.WARNING(f"AI Response: {result}"))
                        continue
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Error parsing AI response for chunk {i+1}: {str(e)}"
                            )
                        )
                        self.stdout.write(self.style.WARNING(f"AI Response: {result}"))
                        continue

                # Process extracted terms
                for term_data in all_terms:
                    if not term_data.get("term") or not term_data.get("definition"):
                        continue

                    SustainabilityGlossary.objects.update_or_create(
                        term=term_data["term"].strip(),
                        defaults={
                            "definition": term_data["definition"].strip(),
                            "source": source["url"],
                            "category": source["category"],
                            "defunct": False,
                            "context": term_data.get("context", None),
                        },
                    )

                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully processed {len(all_terms)} terms from {source["url"]}'
                    )
                )

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing {source["url"]}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS("Glossary loading complete!"))
