import re
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta


class ClaimCategory(Enum):
    ENVIRONMENTAL = "environmental"  # Environmental impact and sustainability claims
    SOCIAL = "social"  # Social responsibility and community impact claims
    GOVERNANCE = "governance"  # Corporate governance and ethical practice claims
    PRODUCT = "product"  # Product-specific environmental or sustainability claims
    GENERAL = "general"  # General corporate sustainability statements


class EvidenceStrength(Enum):
    STRONG = 0  # """Third-party verified claims with specific metrics, certifications, or independent audit reports"""
    MODERATE = (
        1  # """Internal data with partial verification, documented processes or methodologies"""
    )
    WEAK = 2  # """Vague claims, marketing statements without substantial backing"""
    NONE = 3  # """No supporting evidence or purely aspirational statements"""
    MISLEADING = 4  # """Claims that appear deliberately vague or misleading"""


class ClaimImpact(Enum):
    HIGH = 0  # """Company-wide initiatives with measurable global/industry impact (e.g., Carbon neutral across all operations)"""
    MEDIUM = 1  # """Significant but limited scope initiatives (e.g., 50% renewable energy in manufacturing)"""
    LOW = (
        2  # """Small-scale or localized initiatives (e.g., Recycling program at headquarters)"""
    )
    MINIMAL = 3  # """Superficial or negligible impact on sustainability"""
    DECEPTIVE = 4  # """Claims that overstate or misrepresent actual impact"""


@dataclass
class ScoringCriteria:
    category: ClaimCategory
    evidence_strength: EvidenceStrength
    claim_impact: ClaimImpact
    time_relevance: float  # 0-1 score based on how recent the claim is
    consistency_score: float  # 0-1 score based on alignment with other claims


class GreenwashingScorer:
    def __init__(self):
        self.weights = {
            "evidence_strength": 1.75,  # (0-4) * 1.75 = 0-7 points
            "claim_impact": 1.5,  # (0-4) * 1.5 = 0-6 points
            "time_relevance": 0.75,  # (0-1) * 0.75 = 0-0.75 points
            "consistency": 0.75,  # (0-1) * 0.75 = 0-0.75 points
        }

    def calculate_time_relevance(self, claim_date_or_text: str) -> tuple[float, str]:
        """
        Calculate time relevance score based on claim date or text context

        Args:
            claim_date_or_text: Either a date string or text containing temporal information

        Returns:
            tuple[float, str]: (
                score between 0-1,
                explanation of how the score was determined
            )

            Score ranges:
                1.0: Current year/Ongoing
                0.8: Last year
                0.6: 2 years ago
                0.4: 3 years ago
                0.2: 4-5 years ago
                0.0: Over 5 years ago or no time reference
        """
        if not claim_date_or_text:
            return 0.0, "No time reference provided"

        try:
            # First try to parse as exact date
            date = parse(claim_date_or_text, fuzzy=True)
            years_ago = relativedelta(datetime.now(), date).years
            return self._calculate_score_from_years(years_ago)
        except (ValueError, TypeError):
            # If exact date parsing fails, try to extract temporal information from text
            return self._extract_temporal_score(claim_date_or_text)

    def _calculate_score_from_years(self, years_ago: int) -> tuple[float, str]:
        """Calculate score based on number of years ago"""
        if years_ago == 0:
            return 1.0, "Current year"
        elif years_ago == 1:
            return 0.8, "Last year"
        elif years_ago == 2:
            return 0.6, "2 years ago"
        elif years_ago == 3:
            return 0.4, "3 years ago"
        elif years_ago <= 5:
            return 0.2, "4-5 years ago"
        else:
            return 0.0, "Over 5 years ago"

    def _extract_temporal_score(self, text: str) -> tuple[float, str]:
        """Extract temporal information from text and calculate score"""
        text = text.lower()

        # Define temporal patterns and their scores
        temporal_patterns = [
            # Current/Ongoing patterns
            (r"\b(current|ongoing|present|now|today|this year)\b", 1.0, "Current/Ongoing"),
            # Recent past patterns
            (r"\b(last year|previous year|a year ago)\b", 0.8, "Last year"),
            (r"\b(2 years ago|two years ago)\b", 0.6, "2 years ago"),
            (r"\b(3 years ago|three years ago)\b", 0.4, "3 years ago"),
            (r"\b(4|5|four|five) years ago\b", 0.2, "4-5 years ago"),
            # Future commitments (treated as current)
            (r"\b(will|plan|goal|target|commit|by 20\d\d)\b", 1.0, "Future commitment"),
        ]

        # Check each pattern
        for pattern, score, description in temporal_patterns:
            match = re.search(pattern, text)
            if match:
                return score, description

        # Handle year patterns separately to avoid tuple unpacking issues
        year_pattern = r"\b20\d\d\b"
        match = re.search(year_pattern, text)
        if match:
            years_ago = datetime.now().year - int(match.group())
            return self._calculate_score_from_years(years_ago)

        # Recent/Latest patterns
        if re.search(r"\b(recent|latest|newly)\b", text):
            return 0.9, "Recent (unspecified)"

        # Past patterns with lower confidence
        if re.search(r"\b(previously|formerly|past|earlier)\b", text):
            return 0.3, "Past (unspecified)"

        # Look for season/quarter patterns
        if re.search(r"\b(spring|summer|fall|autumn|winter|q[1-4])\b", text):
            return 0.9, "Within last year (season/quarter mentioned)"

        # Default case - no clear temporal information
        if "none" in text or not text.strip():
            return 0.1, "No timeframe provided"

        return 0.5, "Unclear timeframe - assuming ongoing"

    def calculate_consistency(self, claim: str, other_claims: List[str]) -> tuple[float, str]:
        """
        Calculate consistency score based on other claims

        Args:
            claim: The current claim being evaluated
            other_claims: List of other claims from the same company

        Returns:
            tuple[float, str]: (
                score between 0-1,
                explanation of the consistency analysis
            )
        """
        if not other_claims:
            return 0.5, "No other claims available for consistency check"

        # Initialize variables for analysis
        contradictions = []
        supporting_claims = []
        partial_matches = []

        # Convert claim to lowercase for comparison
        claim_lower = claim.lower()

        # Extract key terms from the claim
        claim_terms = set(re.findall(r"\b\w+\b", claim_lower))

        for other_claim in other_claims:
            other_lower = other_claim.lower()
            other_terms = set(re.findall(r"\b\w+\b", other_lower))

            # Calculate term overlap
            overlap = len(claim_terms.intersection(other_terms)) / len(claim_terms)

            # Check for contradictions
            contradiction_patterns = [
                (r"\bnot\b.*\b{}\b", r"\b{}\b"),
                (r"\bno\b.*\b{}\b", r"\b{}\b"),
                (r"\bfail.*\b{}\b", r"\bsuccess.*\b{}\b"),
            ]

            has_contradiction = False
            for pattern_pair in contradiction_patterns:
                if (
                    re.search(pattern_pair[0], claim_lower)
                    and re.search(pattern_pair[1], other_lower)
                ) or (
                    re.search(pattern_pair[0], other_lower)
                    and re.search(pattern_pair[1], claim_lower)
                ):
                    contradictions.append(other_claim)
                    has_contradiction = True
                    break

            if not has_contradiction:
                if overlap > 0.7:
                    supporting_claims.append(other_claim)
                elif overlap > 0.3:
                    partial_matches.append(other_claim)

        # Calculate consistency score
        if contradictions:
            score = max(0.0, 0.3 - (0.1 * len(contradictions)))
            explanation = f"Found {len(contradictions)} contradicting claims"
        elif supporting_claims:
            score = min(1.0, 0.7 + (0.1 * len(supporting_claims)))
            explanation = f"Found {len(supporting_claims)} supporting claims"
        elif partial_matches:
            score = 0.5 + (0.05 * len(partial_matches))
            explanation = f"Found {len(partial_matches)} partially related claims"
        else:
            score = 0.5
            explanation = "No direct contradictions or support found"

        return score, explanation

    def calculate_score(self, criteria: ScoringCriteria) -> Dict:
        """
        Calculate the final score based on all criteria and normalize to 0-10 scale

        Returns:
            Dict containing:
            - total_score: Weighted average of all scores (0-10)
            - Individual component scores
            - Category
        """
        # Calculate raw component scores
        evidence_score = criteria.evidence_strength.value * self.weights["evidence_strength"]
        impact_score = criteria.claim_impact.value * self.weights["claim_impact"]
        time_score = criteria.time_relevance * self.weights["time_relevance"]
        consistency_score = criteria.consistency_score * self.weights["consistency"]

        # Calculate raw total (max possible is 14.5)
        raw_total = evidence_score + impact_score + time_score + consistency_score

        # Normalize to 0-10 scale
        # 14.5 is the maximum possible score: (4 * 1.75) + (4 * 1.5) + (1 * 0.75) + (1 * 0.75)
        normalized_total = min(10, (raw_total / 14.5) * 10)

        return {
            "total_score": normalized_total,
            "evidence_score": evidence_score,
            "impact_score": impact_score,
            "time_score": time_score,
            "consistency_score": consistency_score,
            "category": criteria.category.value,
        }
