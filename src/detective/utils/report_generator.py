import pandas as pd
from typing import Dict, Tuple
from detective.models import RawStatistics, Staging
from django.db.models import Avg, StdDev
from datetime import datetime
from tailslide import Median, Percentile


class ReportGenerator:
    def __init__(self, company_name: str, filename: str, stats: Dict, df: pd.DataFrame):
        self.company_name = company_name
        self.filename = filename
        self.stats = stats
        self.df = df
        self.workbook = None
        self.writer = None

    @staticmethod
    def process_report_data(company_id: int) -> Tuple[dict, pd.DataFrame]:
        """
        Processes the report data for the company with enhanced metrics and insights.
        Returns a tuple of statistics and a pandas DataFrame.
        """
        urls = Staging.objects.filter(company_id=company_id).values_list("url", flat=True)

        # Enhanced statistics calculations
        company_stats = RawStatistics.objects.filter(
            company_id=company_id, defunct=False
        ).order_by("-score")

        # Calculate score breakdown metrics manually
        evidence_scores = []
        impact_scores = []
        time_scores = []
        consistency_scores = []

        for stat in company_stats:
            if stat.score_breakdown:
                evidence_scores.append(stat.score_breakdown.get("evidence", 0))
                impact_scores.append(stat.score_breakdown.get("impact", 0))
                time_scores.append(stat.score_breakdown.get("time_relevance", 0))
                consistency_scores.append(stat.score_breakdown.get("consistency", 0))

        # Calculate averages safely
        avg_evidence = sum(evidence_scores) / len(evidence_scores) if evidence_scores else 0
        avg_impact = sum(impact_scores) / len(impact_scores) if impact_scores else 0
        avg_time = sum(time_scores) / len(time_scores) if time_scores else 0
        avg_consistency = (
            sum(consistency_scores) / len(consistency_scores) if consistency_scores else 0
        )

        stats = {
            "Summary Statistics": {
                "Mean Score": company_stats.aggregate(Avg("score"))["score__avg"],
                "Median Score": company_stats.aggregate(Median("score"))["score__median"],
                "Standard Deviation": company_stats.aggregate(StdDev("score"))["score__stddev"],
                "90th Percentile": company_stats.aggregate(Percentile("score", 0.9))[
                    "score__percentile"
                ],
                "Unique URLs Analyzed": len(set(urls)),
                "Average Evidence Score": avg_evidence,
                "Average Impact Score": avg_impact,
                "Average Time Relevance": avg_time,
                "Average Consistency": avg_consistency,
            },
            "Category Analysis": ReportGenerator._get_category_breakdown(company_stats),
            "Risk Assessment": ReportGenerator._calculate_risk_metrics(company_stats),
            "Temporal Analysis": ReportGenerator._analyze_temporal_trends(company_stats),
            "Recommendations Summary": ReportGenerator._summarize_recommendations(company_stats),
            "Justification Analysis": ReportGenerator._analyze_justifications(company_stats),
        }

        # Enhanced DataFrame with additional columns
        data = {
            "Score": [stat.score for stat in company_stats],
            "Risk Level": [ReportGenerator._get_risk_level(stat.score) for stat in company_stats],
            "Category": [stat.category for stat in company_stats],
            "Claim": [stat.claim for stat in company_stats],
            "Evaluation": [stat.evaluation for stat in company_stats],
            # Get the first staging URL if available
            "URL": [
                stat.staging.first().url if stat.staging.exists() else ""
                for stat in company_stats
            ],
            "Processed Date": [
                datetime.strftime(stat.created_at, "%Y-%m-%d %H:%M:%S") for stat in company_stats
            ],
            "Score Breakdown": [stat.score_breakdown for stat in company_stats],
            "Recommendations": [stat.recommendations for stat in company_stats],
            "Evidence Justification": [
                stat.justification.get("evidence", "") for stat in company_stats
            ],
            "Impact Justification": [
                stat.justification.get("impact", "") for stat in company_stats
            ],
            "Time Context": [
                stat.justification.get("time_context", {}) for stat in company_stats
            ],
            "Consistency Analysis": [
                stat.justification.get("consistency", {}) for stat in company_stats
            ],
        }

        df = pd.DataFrame(data)
        return stats, df

    def generate(self) -> None:
        """Main method to generate the complete report"""
        with pd.ExcelWriter(self.filename, engine="xlsxwriter") as self.writer:
            self.workbook = self.writer.book
            self._create_detailed_analysis_sheet()
            self._create_executive_summary_sheet()
            self._create_justification_analysis_sheet()
            self._create_scoring_rules_sheet()

    def _create_detailed_analysis_sheet(self) -> None:
        """Creates the detailed analysis worksheet"""
        self.df.to_excel(
            self.writer, startrow=0, startcol=0, sheet_name="Detailed Analysis", index=False
        )
        self._format_detailed_sheet()

    def _create_executive_summary_sheet(self) -> None:
        """Creates the executive summary worksheet"""
        overview_df = pd.DataFrame()
        overview_df.to_excel(self.writer, sheet_name="Executive Summary", startrow=0)
        overview_sheet = self.writer.sheets["Executive Summary"]

        # Formatting
        header_format = self.workbook.add_format(
            {"bold": True, "font_size": 14, "bg_color": "#E6E6E6"}
        )
        summary_format = self.workbook.add_format(
            {"text_wrap": True, "valign": "top", "font_size": 12}
        )

        # Write content
        row = 0

        # Generate AI summary
        summary_prompt = f"""
        Generate a concise executive summary for a greenwashing analysis report for {self.company_name}.
        Key metrics:
        - Mean Score: {self.stats['Summary Statistics']['Mean Score']}
        - Median Score: {self.stats['Summary Statistics']['Median Score']}
        - High Risk Claims: {self.stats['Risk Assessment']['High Risk Claims']['percentage']}%
        - Top Categories: {', '.join(list(self.stats['Category Analysis'].keys())[:3])}
        - Trend: {self.stats['Temporal Analysis']['Trend Direction']}

        Focus on the overall risk level, key areas of concern, and main recommendations.
        Keep it to 3-4 sentences maximum.
        """

        try:
            from detective.utils.completion import Completion

            completion = Completion(
                message=summary_prompt,
                rule="You are a sustainability analyst creating executive summaries for greenwashing reports. Be professional and concise.",
            )
            ai_summary = completion.create_completion()
        except Exception as e:
            ai_summary = "Summary unavailable due to technical error"
            self.logger.error(f"Failed to generate AI summary: {str(e)}")

        # Write AI summary
        overview_sheet.write(
            row, 0, f"Greenwashing Analysis Report - {self.company_name}", header_format
        )
        row += 2
        overview_sheet.write(row, 0, "Executive Summary", header_format)
        row += 1
        overview_sheet.write(row, 0, ai_summary, summary_format)
        row += 3

        # Summary Statistics
        overview_sheet.write(row, 0, "Key Metrics", header_format)
        row += 1
        for key, value in self.stats["Summary Statistics"].items():
            overview_sheet.write(row, 0, key)
            overview_sheet.write(row, 1, value)
            row += 1

        # Risk Distribution
        row += 2
        overview_sheet.write(row, 0, "Risk Distribution", header_format)
        row += 1
        risk_data = self.stats["Risk Assessment"]
        for risk_level, data in risk_data.items():
            overview_sheet.write(row, 0, risk_level)
            overview_sheet.write(row, 1, f"{data['percentage']:.1f}%")
            row += 1

        # Category Analysis
        row += 2
        overview_sheet.write(row, 0, "Category Analysis", header_format)
        row += 1
        for category, data in self.stats["Category Analysis"].items():
            overview_sheet.write(row, 0, category)
            overview_sheet.write(row, 1, f"Avg Score: {data['avg_score']:.1f}")
            overview_sheet.write(row, 2, f"High Risk: {data['high_risk_percentage']:.1f}%")
            row += 1

        # Recommendations
        row += 2
        overview_sheet.write(row, 0, "Recommendations", header_format)
        row += 1
        for rec in self.stats["Recommendations Summary"]["Top Recommendations"]:
            overview_sheet.write(row, 0, rec)
            row += 1

        # Temporal Analysis
        row += 2
        overview_sheet.write(row, 0, "Temporal Analysis", header_format)
        row += 1
        for key, value in self.stats["Temporal Analysis"].items():
            overview_sheet.write(row, 0, key)
            overview_sheet.write(row, 1, str(value))
            row += 1

    def _create_justification_analysis_sheet(self) -> None:
        """Creates the justification analysis worksheet"""
        justification_df = pd.DataFrame()
        justification_df.to_excel(self.writer, sheet_name="Justification Analysis", startrow=0)
        justification_sheet = self.writer.sheets["Justification Analysis"]

        # Formatting
        header_format = self.workbook.add_format(
            {"bold": True, "font_size": 14, "bg_color": "#E6E6E6"}
        )
        insight_format = self.workbook.add_format({"bold": True, "font_color": "#1F497D"})

        # Justification Analysis
        row = 0
        justification_sheet.write(row, 0, "Justification Analysis", header_format)
        row += 2

        # Key Insights Section
        justification_sheet.write(row, 0, "Key Insights", insight_format)
        row += 1
        insights = self.stats["Justification Analysis"]["Key Insights"]

        # Evidence Quality Insights
        justification_sheet.write(row, 0, "Evidence Quality Insights:")
        row += 1
        justification_sheet.write(
            row,
            1,
            f"Strongest Evidence: {insights['Evidence Quality']['Strongest Evidence']}",
        )
        row += 1
        justification_sheet.write(
            row, 1, f"Weakest Evidence: {insights['Evidence Quality']['Weakest Evidence']}"
        )
        row += 2

        # Impact Analysis Insights
        justification_sheet.write(row, 0, "Impact Analysis Insights:")
        row += 1
        justification_sheet.write(
            row, 1, f"Most Common Impact: {insights['Impact Analysis']['Most Common Impact']}"
        )
        row += 1
        justification_sheet.write(
            row,
            1,
            f"Least Common Impact: {insights['Impact Analysis']['Least Common Impact']}",
        )
        row += 2

        # Time Context Insights
        justification_sheet.write(row, 0, "Time Context Insights:")
        row += 1
        justification_sheet.write(
            row,
            1,
            f"Most Common Confidence Level: {insights['Time Context']['Most Common Confidence Level']}",
        )
        row += 2

        # Consistency Insights
        justification_sheet.write(row, 0, "Consistency Insights:")
        row += 1
        justification_sheet.write(
            row,
            1,
            f"Percentage with Related Claims: {insights['Consistency']['Percentage with Related Claims']}%",
        )
        row += 1
        justification_sheet.write(
            row,
            1,
            f"Percentage with Analysis: {insights['Consistency']['Percentage with Analysis']}%",
        )

        # Time Context
        row += 2
        justification_sheet.write(row, 0, "Time Context", header_format)
        row += 1
        for key, value in self.stats["Justification Analysis"]["Time Context"].items():
            justification_sheet.write(row, 0, key)
            justification_sheet.write(row, 1, str(value))
            row += 1

        # Consistency
        row += 2
        justification_sheet.write(row, 0, "Consistency", header_format)
        row += 1
        for key, value in self.stats["Justification Analysis"]["Consistency"].items():
            justification_sheet.write(row, 0, key)
            justification_sheet.write(row, 1, str(value))
            row += 1

    def _create_scoring_rules_sheet(self) -> None:
        """Creates the scoring rules explanation worksheet"""
        rules_df = pd.DataFrame()
        rules_df.to_excel(self.writer, sheet_name="Scoring Rules", startrow=0)
        rules_sheet = self.writer.sheets["Scoring Rules"]
        # Formatting
        header_format = self.workbook.add_format(
            {"bold": True, "font_size": 14, "bg_color": "#E6E6E6"}
        )
        section_format = self.workbook.add_format(
            {"bold": True, "font_size": 12, "font_color": "#1F497D"}
        )
        text_format = self.workbook.add_format({"text_wrap": True, "valign": "top"})

        # Write content
        row = 0
        rules_sheet.write(row, 0, "Scoring Rules Explanation", header_format)
        row += 2

        # Overall Scoring Explanation
        rules_sheet.write(row, 0, "How Scores Are Calculated", section_format)
        row += 1
        rules_sheet.write(
            row,
            0,
            """
The overall score is calculated based on four key factors:
1. Evidence Strength (35% weight): How well-supported the claim is
2. Claim Impact (25% weight): The scale and significance of the claim's impact
3. Time Relevance (20% weight): How current and relevant the claim is
4. Consistency (20% weight): How well the claim aligns with other company statements

Each factor is scored individually and then combined to create the overall score.
        """,
            text_format,
        )
        row += 6

        # Evidence Strength
        rules_sheet.write(row, 0, "Evidence Strength", section_format)
        row += 1
        rules_sheet.write(
            row,
            0,
            """
• Strong (3 points): Third-party verified claims with specific metrics, certifications, or independent audit reports
• Moderate (2 points): Internal data with partial verification, documented processes or methodologies
• Weak (1 point): Vague claims, marketing statements without substantial backing
• None (0 points): No supporting evidence or purely aspirational statements
        """,
            text_format,
        )
        row += 6

        # Claim Impact
        rules_sheet.write(row, 0, "Claim Impact", section_format)
        row += 1
        rules_sheet.write(
            row,
            0,
            """
• High (3 points): Company-wide initiatives with measurable global/industry impact
• Medium (2 points): Significant but limited scope initiatives
• Low (1 point): Small-scale or localized initiatives
• Minimal (0 points): Superficial or negligible impact on sustainability
        """,
            text_format,
        )
        row += 6

        # Time Relevance
        rules_sheet.write(row, 0, "Time Relevance", section_format)
        row += 1
        rules_sheet.write(
            row,
            0,
            """
• Current year/Ongoing: 1.0
• Last year: 0.8
• 2 years ago: 0.6
• 3 years ago: 0.4
• 4-5 years ago: 0.2
• Over 5 years ago: 0.0
        """,
            text_format,
        )
        row += 6

        # Consistency
        rules_sheet.write(row, 0, "Consistency", section_format)
        row += 1
        rules_sheet.write(
            row,
            0,
            """
• 1.0: Multiple supporting claims with no contradictions
• 0.7-0.9: Generally consistent with other claims
• 0.5: Neutral - no clear support or contradiction
• 0.3-0.4: Some contradictions present
• 0.0-0.2: Significant contradictions with other claims
        """,
            text_format,
        )
        row += 6

        # Risk Levels
        rules_sheet.write(row, 0, "Risk Levels", section_format)
        row += 1
        rules_sheet.write(
            row,
            0,
            """
• High Risk (7-10): Claims with weak evidence, high potential for greenwashing
• Medium Risk (4-6.9): Claims with some evidence but room for improvement
• Low Risk (0-3.9): Well-supported claims with minimal greenwashing risk
        """,
            text_format,
        )

        # Adjust column width for readability
        rules_sheet.set_column("A:A", 50)

    def _format_detailed_sheet(self) -> None:
        """Applies formatting to the detailed analysis worksheet"""
        worksheet = self.writer.sheets["Detailed Analysis"]

        # Add conditional formatting for risk levels
        red_format = self.workbook.add_format({"bg_color": "#FFC7CE"})
        yellow_format = self.workbook.add_format({"bg_color": "#FFEB9C"})
        green_format = self.workbook.add_format({"bg_color": "#C6EFCE"})

        score_col = self.df.columns.get_loc("Score")
        worksheet.conditional_format(
            0,
            score_col,
            len(self.df),
            score_col,
            {"type": "cell", "criteria": ">=", "value": 7, "format": red_format},
        )
        worksheet.conditional_format(
            0,
            score_col,
            len(self.df),
            score_col,
            {
                "type": "cell",
                "criteria": "between",
                "minimum": 4,
                "maximum": 6.99,
                "format": yellow_format,
            },
        )
        worksheet.conditional_format(
            0,
            score_col,
            len(self.df),
            score_col,
            {"type": "cell", "criteria": "<", "value": 4, "format": green_format},
        )

    @staticmethod
    def _get_category_breakdown(stats) -> dict:
        """Analyzes claims by category with detailed metrics."""
        category_data = {}
        for stat in stats:
            category = stat.category or "Uncategorized"
            if category not in category_data:
                category_data[category] = {"count": 0, "avg_score": 0, "high_risk_claims": 0}

            category_data[category]["count"] += 1
            category_data[category]["avg_score"] += stat.score
            if stat.score >= 7:  # High risk threshold
                category_data[category]["high_risk_claims"] += 1

        # Calculate averages and percentages
        for category in category_data:
            count = category_data[category]["count"]
            category_data[category]["avg_score"] /= count
            category_data[category]["high_risk_percentage"] = (
                category_data[category]["high_risk_claims"] / count * 100
            )

        return category_data

    @staticmethod
    def _calculate_risk_metrics(stats) -> dict:
        """Calculates detailed risk metrics."""
        total_claims = len(stats)
        if total_claims == 0:
            return {
                "High Risk Claims": {
                    "count": 0,
                    "percentage": 0,
                    "threshold": "Score >= 7",
                },
                "Medium Risk Claims": {
                    "count": 0,
                    "percentage": 0,
                    "threshold": "4 <= Score < 7",
                },
                "Low Risk Claims": {
                    "count": 0,
                    "percentage": 0,
                    "threshold": "Score < 4",
                },
            }

        high_risk = sum(1 for stat in stats if stat.score >= 7)
        medium_risk = sum(1 for stat in stats if 4 <= stat.score < 7)
        low_risk = sum(1 for stat in stats if stat.score < 4)

        return {
            "High Risk Claims": {
                "count": high_risk,
                "percentage": (high_risk / total_claims * 100),
                "threshold": "Score >= 7",
            },
            "Medium Risk Claims": {
                "count": medium_risk,
                "percentage": (medium_risk / total_claims * 100),
                "threshold": "4 <= Score < 7",
            },
            "Low Risk Claims": {
                "count": low_risk,
                "percentage": (low_risk / total_claims * 100),
                "threshold": "Score < 4",
            },
        }

    @staticmethod
    def _analyze_temporal_trends(stats) -> dict:
        """Analyzes trends over time."""
        # Create DataFrame with dates
        df = pd.DataFrame(
            [{"date": stat.created_at.date(), "score": stat.score} for stat in stats]
        )

        if not df.empty:
            # Set date as index and sort
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()

            # Calculate weekly averages
            weekly_avg = df.resample("W")["score"].mean()

            trend_direction = "No Change"
            if len(weekly_avg) > 1:
                trend_direction = (
                    "Increasing" if weekly_avg.iloc[-1] > weekly_avg.iloc[0] else "Decreasing"
                )

            return {
                "Weekly Averages": weekly_avg.to_dict(),
                "Trend Direction": trend_direction,
                "Score Volatility": df["score"].std(),
            }
        return {
            "Weekly Averages": {},
            "Trend Direction": "Insufficient Data",
            "Score Volatility": 0,
        }

    @staticmethod
    def _summarize_recommendations(stats) -> dict:
        """Summarizes common recommendations and improvement areas."""
        recommendations = [stat.recommendations for stat in stats if stat.recommendations]
        return {
            "Top Recommendations": ReportGenerator._get_top_recommendations(recommendations),
            "Priority Areas": ReportGenerator._identify_priority_areas(stats),
        }

    @staticmethod
    def _get_risk_level(score: float) -> str:
        """Determines risk level based on score."""
        if score >= 7:
            return "High Risk"
        elif score >= 4:
            return "Medium Risk"
        return "Low Risk"

    @staticmethod
    def _get_top_recommendations(recommendations: list) -> dict:
        """
        Analyzes and returns the most common recommendations.
        """
        # Flatten list of recommendations if they're nested
        flat_recommendations = []
        for rec_list in recommendations:
            if isinstance(rec_list, list):
                flat_recommendations.extend(rec_list)
            else:
                flat_recommendations.append(rec_list)

        # Count occurrences of each recommendation
        recommendation_counts = {}
        for rec in flat_recommendations:
            if rec:  # Skip empty recommendations
                if rec not in recommendation_counts:
                    recommendation_counts[rec] = 0
                recommendation_counts[rec] += 1

        # Sort by frequency and get top 5
        sorted_recommendations = sorted(
            recommendation_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]

        return {
            "Most Common": dict(sorted_recommendations),
            "Total Count": len(flat_recommendations),
        }

    @staticmethod
    def _identify_priority_areas(stats) -> dict:
        """
        Identifies priority areas based on high-risk claims and categories.
        """
        # Track categories with high-risk claims
        category_risks = {}
        high_risk_claims = []

        for stat in stats:
            category = stat.category or "Uncategorized"

            # Initialize category if not exists
            if category not in category_risks:
                category_risks[category] = {
                    "high_risk_count": 0,
                    "total_count": 0,
                    "avg_score": 0,
                }

            # Update category statistics
            category_risks[category]["total_count"] += 1
            category_risks[category]["avg_score"] += stat.score

            # Track high-risk claims
            if stat.score >= 7:
                category_risks[category]["high_risk_count"] += 1
                high_risk_claims.append(
                    {"category": category, "score": stat.score, "claim": stat.claim}
                )

        # Calculate averages and identify priority categories
        priority_categories = []
        for category, data in category_risks.items():
            if data["total_count"] > 0:
                data["avg_score"] /= data["total_count"]
                if data["high_risk_count"] > 0 or data["avg_score"] >= 6:
                    priority_categories.append(
                        {
                            "category": category,
                            "high_risk_count": data["high_risk_count"],
                            "avg_score": data["avg_score"],
                        }
                    )

        # Sort priority categories by high risk count and average score
        priority_categories.sort(
            key=lambda x: (x["high_risk_count"], x["avg_score"]), reverse=True
        )

        return {
            "Priority Categories": priority_categories[:3],  # Top 3 priority categories
            "High Risk Claims Count": len(high_risk_claims),
            "Categories Needing Attention": len(
                [c for c in priority_categories if c["avg_score"] >= 6]
            ),
        }
