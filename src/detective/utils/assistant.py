from openai import OpenAI
from tempfile import NamedTemporaryFile
import logging
import os
from django.db import transaction
from detective.models import Run, Staging, RawStatistics
from detective.utils.scoring_rules import ClaimCategory, EvidenceStrength, ClaimImpact
from detective.utils.run.pre import PreRunProcessor
from detective.utils.run.post import PostRunProcessor


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
        self.stat_data = RawStatistics.objects.get(uuid=stat_uuid) if stat_uuid else None
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

    def _generate_scoring_guidelines(self):
        """Generate scoring guidelines based on scoring rules"""
        return f"""
        Please analyze each environmental claim using the following structured format and criteria.
        Provide your response in JSON format with detailed scoring for each claim:

        1. Evidence Strength (0-4, higher score = higher greenwashing risk):
           {self._format_enum_values(EvidenceStrength)}
           Note: Higher scores indicate higher greenwashing risk. Vague marketing claims should receive high scores.

        2. Claim Impact (0-4, higher score = higher greenwashing risk):
           {self._format_enum_values(ClaimImpact)}
           Note: Higher scores indicate higher greenwashing risk. Claims that overstate or misrepresent impact should receive high scores.

        3. Category Classification:
           {self._format_enum_values(ClaimCategory)}

        4. Time Relevance Scoring (0-1):
           When exact dates aren't available, look for temporal indicators:
           - Current/Ongoing initiatives: 0.8-1.0
           - Recent past (within 1 year): 0.7-0.9
           - Medium past (1-3 years): 0.4-0.6
           - Older claims (3-5 years): 0.2-0.3
           - No time reference: 0.1

           Consider:
           - Specific dates or years mentioned
           - Words like "current", "ongoing", "recent"
           - Future commitments and target dates
           - Seasonal or quarterly references

        5. Consistency Analysis (0-1):
           Look for:
           - Supporting claims that reinforce each other
           - Contradicting statements or numbers
           - Overlapping initiatives
           - Progressive improvements over time

           Score based on:
           - Perfect alignment: 0.8-1.0
           - Partial support: 0.6-0.8
           - Neutral/Independent: 0.5
           - Minor conflicts: 0.3-0.4
           - Major contradictions: 0.0-0.2

        Important Scoring Notes:
        - Higher scores indicate HIGHER greenwashing risk
        - Vague marketing language should receive high evidence and impact scores
        - Claims without specific metrics or verification should receive high scores
        - Marketing slogans or broad statements should be scored as MISLEADING (4) for evidence
        - Claims that overstate environmental impact should be scored as DECEPTIVE (4) for impact
        - Example: "Curated for Earth Lovers" should receive high scores (MISLEADING evidence, DECEPTIVE impact) due to vague marketing language

        Please structure your response in the following JSON format:

        {{
            "claims": [
                {{
                    "claim": "Full claim text",
                    "category": "{' | '.join(cat.value for cat in ClaimCategory)}",
                    "evidence_strength": {{
                        "score": 0-4,
                        "justification": "Detailed explanation of evidence rating"
                    }},
                    "impact": {{
                        "score": 0-4,
                        "justification": "Explanation of impact assessment"
                    }},
                    "time_relevance": {{
                        "date": "YYYY-MM-DD or time period",
                        "score": 0-1,
                        "notes": "Time context explanation",
                        "confidence": "high|medium|low"
                    }},
                    "consistency": {{
                        "score": 0-1,
                        "analysis": "Detailed consistency analysis",
                        "related_claims": ["list", "of", "related", "claims"]
                    }},
                    "evaluation": "Detailed evaluation of the claim",
                    "recommendations": "Specific recommendations for improvement"
                }}
            ]
        }}
        """

    def _format_enum_values(self, enum_class):
        """Format enum values into readable guidelines"""
        return "\n           ".join(
            f'- {name} ({value.value}): {value.__doc__ if value.__doc__ else name.replace("_", " ").title()}'
            for name, value in enum_class.__members__.items()
        )

    def trigger_staging_run(self):
        """
        Trigger a run for a thread
        """
        try:
            with transaction.atomic():
                if self.staging_data.processed == Staging.STATUS_PROCESSED:
                    self.logger.info(f"Staging data already processed: {self.staging_data.uuid}")
                    return

                url = self.staging_data.url
                knowledge = self.staging_data.raw
                company = self.staging_data.company

                # Generate scoring guidelines from rules
                scoring_guidelines = self._generate_scoring_guidelines()

                messages = [
                    {
                        "role": "user",
                        "content": f"""This is the raw data for the url: {url}. Before processing any greenwashing claims, keep in mind what the company does.

                        Company: {company.name}
                        Description: {company.about_summary}

                        {scoring_guidelines}

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
        Trigger a run for a thread to analyze claim consistency and specificity
        """
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
                current_claim = self.stat_data.claim
                current_evaluation = self.stat_data.evaluation
                similar_claims, similar_evaluations = self.stat_data.find_similar_claims(limit=10)
                company = self.staging_data.company

                claim_analysis_guidelines = """
                Please analyze if the current claim should be marked as defunct based on the following criteria:

                Important Considerations:
                - Preserve claims that might indicate potential greenwashing
                - Keep claims that represent different aspects of sustainability
                - Maintain claims that provide unique context or perspective
                - Only mark as defunct when there is clear evidence of redundancy or supersession

                1. Specificity Comparison:
                   - More specific claims supersede general claims
                   - Claims with concrete metrics/numbers are preferred over qualitative claims
                   - Claims with verification methods or standards mentioned take precedence

                2. Evidence Strength Hierarchy:
                   a) Third-party verified claims with specific metrics
                   b) Internal data with concrete numbers
                   c) General sustainability statements
                   d) Marketing claims without specifics

                3. Claim Relationship Analysis:
                   - SUPERSEDING: Newer claim provides more detail about the same topic
                   - SUPPORTING: Claims that add complementary information
                   - CONTRADICTING: Claims that present conflicting information
                   - DUPLICATING: Multiple instances of the same claim

                4. Defunct Criteria (Mark current claim as defunct ONLY if):
                   - A more specific claim exists about the same topic AND provides clear evidence of reduced greenwashing risk
                   - Another claim provides concrete metrics while current claim is qualitative AND the metrics directly address greenwashing concerns
                   - Another claim has stronger evidence/verification AND it clearly reduces greenwashing risk
                   - Current claim is contradicted by more authoritative claims AND the contradiction reduces greenwashing risk
                   - Current claim is a subset of a more comprehensive claim AND the comprehensive claim addresses greenwashing concerns

                5. Keep Claim Criteria (Do NOT mark as defunct if):
                   - The claim represents a unique aspect of sustainability
                   - The claim provides context not found in other claims
                   - The claim might indicate potential greenwashing
                   - The claim is duplicated but appears in different contexts
                   - The claim is qualitative but represents an important sustainability aspect

                Please analyze the following claim against related claims and provide your response in this JSON format:

                {
                    "defunct": boolean,  // true if claim should be marked as defunct
                    "scoring": {
                        "claim": "Current claim text",
                        "category": "environmental|social|governance|product|general",
                        "relationship_analysis": {
                            "superseded_by": [
                                {
                                    "claim": "text of superseding claim",
                                    "reason": "Detailed explanation of why this claim supersedes"
                                }
                            ],
                            "supported_by": [
                                {
                                    "claim": "text of supporting claim",
                                    "reason": "How this claim provides support"
                                }
                            ],
                            "contradicted_by": [
                                {
                                    "claim": "text of contradicting claim",
                                    "reason": "Nature of contradiction"
                                }
                            ]
                        },
                        "specificity_comparison": {
                            "current_claim_metrics": ["list", "of", "metrics"],
                            "related_claims_metrics": ["list", "of", "metrics"],
                            "comparative_analysis": "Detailed analysis of specificity differences"
                        },
                        "evidence_strength": {
                            "score": 0-3,
                            "justification": "Analysis of evidence quality"
                        },
                        "recommendation": "Detailed explanation of the decision"
                    }
                }

                Example defunct case:
                Current claim: "Our product is eco-friendly"
                Related claim: "Our product reduces carbon footprint by 30% through sustainable materials, verified by Environmental Agency"
                Decision: Mark as defunct because the related claim provides specific metrics and third-party verification.

                Example keep case:
                Current claim: "We offer a wide range of sustainable products"
                Related claim: "Our products are made from 100% recycled materials"
                Decision: Keep current claim as it provides broader context about product range
                """

                messages = [
                    {
                        "role": "user",
                        "content": f"""Analyze if this claim should be marked as defunct based on other claims from the same company.

                        Company: {company.name}
                        Description: {company.about_summary}
                        URL: {raw}

                        Current Claim: {current_claim}
                        Current Evaluation: {current_evaluation}

                        Related Claims and Evaluations:
                        Similar Claims: {similar_claims}
                        Similar Evaluations: {similar_evaluations}

                        {claim_analysis_guidelines}
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
        return self.client.threads.create(messages=messages)

    def create_run(self, thread_id):
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
            self.start_processing_run(self.staging_data.uuid, run_instance.run_uuid)
            if self.type == self.ASSISTANT_TYPE_PRE
            else None
        )
        (
            self.start_processing_run(
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
        temp_json_file = NamedTemporaryFile(delete=True, suffix=".csv", prefix=file_name)
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
        return self.client.threads.messages.retrieve(thread_id=thread_id, message_id=message_id)

    def start_processing_run(self, staging_uuid, run_uuid, stat_uuid=None, pre_process=True):
        """Process run for a thread."""
        processor_class = PreRunProcessor if pre_process else PostRunProcessor
        processor = processor_class(staging_uuid, run_uuid, stat_uuid)
        processor.start_processing()
