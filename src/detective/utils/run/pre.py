import json
import logging
from detective.utils.run.base import BaseRunProcessor
from detective.models import Staging, RawStatistics
from detective.utils.scoring_rules import GreenwashingScorer
from utils.retry import retry_on_transaction_failure
from detective.utils.scoring_rules import (
    ScoringCriteria,
    ClaimCategory,
    EvidenceStrength,
    ClaimImpact,
)

logger = logging.getLogger(__name__)


class PreRunProcessor(BaseRunProcessor):
    def _process_run_steps(self, assistant, thread_oa_id, steps):
        logger.info(f"Processing run steps for thread: {thread_oa_id}")
        scorer = GreenwashingScorer()

        message_oa_ids = []
        for step in steps:
            if step.step_details.type == "message_creation":
                message_oa_ids.append(step.step_details.message_creation.message_id)

        message_oa_ids.reverse()

        for message_oa_id in message_oa_ids:
            message = assistant.retrieve_message(thread_oa_id, message_oa_id)
            for content in message.content:
                if content.type == "text":
                    try:
                        content_data = json.loads(content.text.value)
                        claims_data = self._extract_claims_data(content_data)

                        if claims_data:
                            processed_claims = self._process_claims_with_scoring(
                                claims_data, scorer
                            )
                            self._save_statistic(processed_claims)
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON parsing error: {e}")
                    except Exception as e:
                        logger.error(f"Error processing content: {e}")

    def _handle_failure(self):
        self._save_staging_status(self.staging_uuid, Staging.STATUS_FAILED)

    @staticmethod
    def _extract_claims_data(content_data):
        if isinstance(content_data, dict):
            for key in ["claims", "greenwashing_claims", "data", "results"]:
                if key in content_data:
                    return content_data[key]
            if "0" in content_data:
                return content_data["0"]
        return content_data if isinstance(content_data, list) else []

    def _process_claims_with_scoring(self, claims_data, scorer):
        """Process claims with the new scoring system"""
        processed_claims = []

        for claim_data in claims_data:
            try:
                # Extract time relevance data, handling nested structure
                time_relevance = claim_data.get("time_relevance", {})
                if isinstance(time_relevance, dict):
                    time_date = time_relevance.get("date", "")
                    time_notes = time_relevance.get("notes", "")
                    time_confidence = time_relevance.get(
                        "confidence", "low"
                    )  # Get confidence from input if available
                else:
                    time_date = ""
                    time_notes = ""
                    time_confidence = "low"

                # Calculate time relevance score - handle both 2 and 3 return values
                time_result = scorer.calculate_time_relevance(time_date or time_notes)
                # Handle both return value formats
                if isinstance(time_result, tuple):
                    if len(time_result) == 3:
                        time_score, time_explanation, time_confidence = time_result
                    else:
                        time_score, time_explanation = time_result
                else:
                    # Handle case where it returns a single score
                    time_score = time_result
                    time_explanation = "Time relevance calculated"

                # Extract consistency data, handling nested structure
                consistency_data = claim_data.get("consistency", {})
                if isinstance(consistency_data, dict):
                    related_claims = consistency_data.get("related_claims", [])
                else:
                    related_claims = []

                # Calculate consistency score
                consistency_score, consistency_explanation = scorer.calculate_consistency(
                    claim_data.get("claim", ""), related_claims
                )

                # Extract evidence and impact data, handling nested structure
                evidence_data = claim_data.get("evidence_strength", {})
                if isinstance(evidence_data, dict):
                    evidence_strength = evidence_data.get("score", "LOW")
                else:
                    evidence_strength = "LOW"

                impact_data = claim_data.get("impact", {})
                if isinstance(impact_data, dict):
                    impact_score = impact_data.get("score", "LOW")
                else:
                    impact_score = "LOW"

                # Create scoring criteria
                criteria = ScoringCriteria(
                    category=ClaimCategory(claim_data.get("category", "GENERAL")),
                    evidence_strength=EvidenceStrength(evidence_strength),
                    claim_impact=ClaimImpact(impact_score),
                    time_relevance=time_score,
                    consistency_score=consistency_score,
                )

                # Calculate final score
                score_details = scorer.calculate_score(criteria)

                processed_claim = {
                    "claim": claim_data.get("claim", ""),
                    "evaluation": claim_data.get("evaluation", ""),
                    "score": score_details["total_score"],
                    "score_breakdown": {
                        "evidence": score_details["evidence_score"],
                        "impact": score_details["impact_score"],
                        "time_relevance": score_details["time_score"],
                        "consistency": score_details["consistency_score"],
                    },
                    "category": criteria.category.value,
                    "justification": {
                        "evidence": evidence_data.get("justification", ""),
                        "impact": impact_data.get("justification", ""),
                        "time_context": {
                            "explanation": time_explanation,
                            "date": time_date,
                            "confidence": time_confidence,
                            "notes": time_notes,
                        },
                        "consistency": {
                            "explanation": consistency_explanation,
                            "related_claims": related_claims,
                            "analysis": consistency_data.get("analysis", ""),
                        },
                    },
                    "recommendations": claim_data.get("recommendations", ""),
                }

                processed_claims.append(processed_claim)

            except Exception as e:
                logger.error(f"Error processing claim: {e}")
                logger.error(f"Problematic claim data: {claim_data}")
                continue

        return processed_claims

    @retry_on_transaction_failure(max_retries=3)
    def _save_statistic(self, processed_claims):
        """Save processed statistics in db with enhanced scoring"""
        try:
            staging = Staging.objects.get(uuid=self.staging_uuid)

            for claim_data in processed_claims:
                try:
                    stat_data = {
                        "evaluation": claim_data["evaluation"],
                        "score": claim_data["score"],
                        "score_breakdown": claim_data["score_breakdown"],
                        "category": claim_data["category"],
                        "justification": claim_data["justification"],
                        "recommendations": claim_data["recommendations"],
                    }

                    # Create the RawStatistics instance without the many-to-many field
                    stat = RawStatistics.objects.create(
                        company=staging.company, claim=claim_data["claim"], **stat_data
                    )

                    # Add the staging relationship after creation
                    stat.staging.add(staging)

                except Exception as item_error:
                    logger.error(f"Failed to save individual statistic: {item_error}")
                    logger.error(f"Problematic claim data: {claim_data}")
                    continue

            self._save_staging_status(self.staging_uuid, Staging.STATUS_PROCESSED)

        except Exception as e:
            logger.error(f"Failed to save statistics batch: {e}")
            raise
