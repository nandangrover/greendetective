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
                # Time relevance processing
                time_relevance = claim_data.get("time_relevance", {})
                time_date = (
                    time_relevance.get("date", "") if isinstance(time_relevance, dict) else ""
                )
                time_notes = (
                    time_relevance.get("notes", "") if isinstance(time_relevance, dict) else ""
                )
                time_confidence = (
                    time_relevance.get("confidence", "low")
                    if isinstance(time_relevance, dict)
                    else "low"
                )

                # Handle the case where time_relevance already has a score
                if isinstance(time_relevance, dict) and "score" in time_relevance:
                    time_score = float(time_relevance["score"])
                    time_explanation = time_notes or "Time relevance from provided score"
                else:
                    # Calculate time relevance if not provided
                    time_result = scorer.calculate_time_relevance(time_date or time_notes)
                    if isinstance(time_result, tuple):
                        time_score, time_explanation = time_result
                    else:
                        time_score = float(time_result)
                        time_explanation = "Time relevance calculated"

                # Ensure time_confidence is set
                if not time_confidence:
                    time_confidence = "low"

                # Consistency processing
                consistency_data = claim_data.get("consistency", {})
                related_claims = (
                    consistency_data.get("related_claims", [])
                    if isinstance(consistency_data, dict)
                    else []
                )

                # Handle the case where consistency already has a score
                if isinstance(consistency_data, dict) and "score" in consistency_data:
                    consistency_score = float(consistency_data["score"])
                    consistency_explanation = consistency_data.get(
                        "analysis", "Consistency from provided score"
                    )
                else:
                    # Calculate consistency if not provided
                    consistency_result = scorer.calculate_consistency(
                        claim_data.get("claim", ""), related_claims
                    )
                    consistency_score, consistency_explanation = consistency_result

                # Extract evidence and impact data, handling nested structure
                evidence_data = claim_data.get("evidence_strength", {})
                if isinstance(evidence_data, dict):
                    evidence_result = evidence_data.get("score", EvidenceStrength.WEAK)
                    # Map numeric scores to enum values
                    if isinstance(evidence_result, (int, float)):
                        if evidence_result >= 3:
                            evidence_strength = EvidenceStrength.STRONG
                        elif evidence_result >= 2:
                            evidence_strength = EvidenceStrength.MODERATE
                        else:
                            evidence_strength = EvidenceStrength.WEAK
                    else:
                        # If it's not a number, just use the default
                        evidence_strength = EvidenceStrength.WEAK
                else:
                    evidence_strength = EvidenceStrength.WEAK

                impact_data = claim_data.get("impact", {})
                if isinstance(impact_data, dict):
                    impact_result = impact_data.get("score", ClaimImpact.LOW)
                    # Map numeric scores to enum values
                    if isinstance(impact_result, (int, float)):
                        if impact_result >= 3:
                            impact_score = ClaimImpact.HIGH
                        elif impact_result >= 2:
                            impact_score = ClaimImpact.MEDIUM
                        else:
                            impact_score = ClaimImpact.LOW
                    else:
                        # If it's not a number, just use the default
                        impact_score = ClaimImpact.LOW
                else:
                    impact_score = ClaimImpact.LOW

                # Create scoring criteria
                try:
                    criteria = ScoringCriteria(
                        category=ClaimCategory(claim_data.get("category", "GENERAL")),
                        evidence_strength=evidence_strength,
                        claim_impact=impact_score,
                        time_relevance=time_score,
                        consistency_score=consistency_score,
                    )
                except ValueError as ve:
                    logger.error(f"Invalid scoring criteria values: {ve}")
                    continue

                # Calculate final score
                score_result = scorer.calculate_score(criteria)
                if isinstance(score_result, dict):
                    score_details = score_result
                else:
                    # If it returns a tuple or other format, construct the score details
                    if isinstance(score_result, tuple):
                        total_score = score_result[0]
                        score_details = {
                            "total_score": total_score,
                            "evidence_score": criteria.evidence_strength.value,
                            "impact_score": criteria.claim_impact.value,
                            "time_score": criteria.time_relevance,
                            "consistency_score": criteria.consistency_score,
                        }
                    else:
                        total_score = float(score_result)
                        score_details = {
                            "total_score": total_score,
                            "evidence_score": criteria.evidence_strength.value,
                            "impact_score": criteria.claim_impact.value,
                            "time_score": criteria.time_relevance,
                            "consistency_score": criteria.consistency_score,
                        }

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
