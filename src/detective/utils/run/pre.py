import json
import traceback
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
        """Process claims with fault-tolerant scoring system"""
        processed_claims = []

        for claim_data in claims_data:
            try:
                if not claim_data.get("claim"):
                    logger.warning("Skipping claim with no claim text")
                    continue

                # Extract evidence strength data with defaults
                evidence_data = claim_data.get("evidence_strength", {})
                if isinstance(evidence_data, (int, float)):
                    evidence_strength = EvidenceStrength(min(int(evidence_data), 4))
                else:
                    evidence_score = evidence_data.get("score", 2)
                    evidence_strength = EvidenceStrength(min(int(evidence_score), 4))

                # Extract impact data with defaults
                impact_data = claim_data.get("impact", {})
                if isinstance(impact_data, (int, float)):
                    claim_impact = ClaimImpact(min(int(impact_data), 4))
                else:
                    impact_score = impact_data.get("score", 2)
                    claim_impact = ClaimImpact(min(int(impact_score), 4))

                # Extract time relevance data with defaults
                time_data = claim_data.get("time_relevance", {})
                time_date = time_data.get("date", "Current/Ongoing")
                time_score, time_explanation = scorer.calculate_time_relevance(time_date)
                time_confidence = time_data.get("confidence", "medium")
                time_notes = time_data.get("notes", "Timeframe inferred from context")

                # Extract consistency data with defaults
                consistency_data = claim_data.get("consistency", {})
                if isinstance(consistency_data, (int, float)):
                    consistency_score = float(consistency_data)
                else:
                    consistency_score = float(consistency_data.get("score", 0.5))
                consistency_explanation = consistency_data.get(
                    "analysis", "Consistency analysis not provided"
                )
                related_claims = consistency_data.get("related_claims", [])

                # Determine category with default
                category_str = claim_data.get("category", "general").upper()
                try:
                    category = ClaimCategory[category_str]
                except (KeyError, ValueError):
                    category = ClaimCategory.GENERAL

                # Create scoring criteria
                criteria = ScoringCriteria(
                    category=category,
                    evidence_strength=evidence_strength,
                    claim_impact=claim_impact,
                    time_relevance=time_score,
                    consistency_score=consistency_score,
                )

                # Calculate final scores
                score_details = scorer.calculate_score(criteria)

                processed_claim = {
                    "claim": claim_data["claim"],
                    "evaluation": claim_data.get("evaluation", "No evaluation provided"),
                    "score": score_details["total_score"],
                    "score_breakdown": {
                        "evidence": score_details["evidence_score"],
                        "impact": score_details["impact_score"],
                        "time_relevance": score_details["time_score"],
                        "consistency": score_details["consistency_score"],
                    },
                    "category": score_details["category"],
                    "justification": {
                        "evidence": evidence_data.get(
                            "justification", "No evidence justification provided"
                        ),
                        "impact": impact_data.get(
                            "justification", "No impact justification provided"
                        ),
                        "time_context": {
                            "explanation": time_explanation,
                            "date": time_date,
                            "confidence": time_confidence,
                            "notes": time_notes,
                        },
                        "consistency": {
                            "explanation": consistency_explanation,
                            "related_claims": related_claims,
                            "analysis": consistency_data.get(
                                "analysis", "No consistency analysis provided"
                            ),
                        },
                    },
                    "recommendations": claim_data.get(
                        "recommendations", "No specific recommendations provided"
                    ),
                }

                processed_claims.append(processed_claim)

            except Exception:
                logger.error(f"Error processing claim: {traceback.format_exc()}")
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
                    # Check if evaluation is empty
                    if not claim_data.get("evaluation", "").strip():
                        raise ValueError("Empty evaluation found in claim data")

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
