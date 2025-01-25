import logging
import os
import pandas as pd
from detective.models import Report
from datetime import datetime
from detective.models import Company, RawStatistics, Staging
from django.db.models import Avg, StdDev
from tailslide import Median, Percentile
from celery import chord, group
from typing import Optional, Tuple


logger = logging.getLogger(__name__)


class StatisticsProcessor:
    def __init__(self, company_id: int) -> None:
        """
        Initializes the StatisticsProcessor with the given company_id.
        """
        self.logger = logging.getLogger(__name__)

        self.company_id = company_id

    def create_raw_statistics(self) -> None:
        """
        Creates raw statistics for the company.
        """
        from detective.tasks import trigger_staging_assistant, check_staging_completion

        # get all staging uuids for a company from staging which have not been processed
        staging_data = Staging.objects.filter(
            company_id=self.company_id, processed=Staging.STATUS_PENDING, defunct=False
        ).values_list("uuid", flat=True)

        # Create a list of tasks with staggered delays
        tasks = []
        wait_time = 0
        for staging_uuid in staging_data:
            tasks.append(trigger_staging_assistant.s(staging_uuid).set(countdown=wait_time))
            wait_time += 10

        # Instead of chord, use group and schedule a separate completion check
        if tasks:
            logger.info("Raw statistics processing started")
            logger.info(f"Processing raw statistics for company {self.company_id}")
            group(tasks).apply_async()
            # Schedule completion check task
            check_staging_completion.apply_async(
                args=[self.company_id],
                countdown=wait_time + 300,  # Start checking 5 minutes after last task
            )

    def process_raw_statistics(self) -> None:
        """
        Processes raw statistics for the company.
        """
        from detective.tasks import (
            trigger_statistic_assistant,
            check_statistics_completion,
        )

        raw_statistics = RawStatistics.objects.filter(
            company_id=self.company_id,
            defunct=False,
            processed=RawStatistics.STATUS_PENDING,
        ).values_list("uuid", flat=True)

        tasks = []
        wait_time = 0
        for stat_uuid in raw_statistics:
            tasks.append(trigger_statistic_assistant.s(stat_uuid).set(countdown=wait_time))
            wait_time += 10

        if tasks:
            logger.info("Processing raw statistics started")
            logger.info(f"Processing company statistics for company {self.company_id}")
            group(tasks).apply_async()
            # Schedule completion check task
            check_statistics_completion.apply_async(
                args=[self.company_id],
                countdown=wait_time + 300,  # Start checking 5 minutes after last task
            )

    def process_report_data(self) -> Tuple[dict, pd.DataFrame]:
        """
        Processes the report data for the company with enhanced metrics and insights.
        Returns a tuple of statistics and a pandas DataFrame.
        """
        urls = Staging.objects.filter(company_id=self.company_id).values_list("url", flat=True)

        # Enhanced statistics calculations
        company_stats = RawStatistics.objects.filter(
            company_id=self.company_id, defunct=False
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
            "Category Analysis": self._get_category_breakdown(company_stats),
            "Risk Assessment": self._calculate_risk_metrics(company_stats),
            "Temporal Analysis": self._analyze_temporal_trends(company_stats),
            "Recommendations Summary": self._summarize_recommendations(company_stats),
            "Justification Analysis": self._analyze_justifications(company_stats),
        }

        # Enhanced DataFrame with additional columns
        data = {
            "Score": [stat.score for stat in company_stats],
            "Risk Level": [self._get_risk_level(stat.score) for stat in company_stats],
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

    def _get_category_breakdown(self, stats) -> dict:
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

    def _calculate_risk_metrics(self, stats) -> dict:
        """Calculates detailed risk metrics."""
        total_claims = len(stats)
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

    def _analyze_temporal_trends(self, stats) -> dict:
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

    def _summarize_recommendations(self, stats) -> dict:
        """Summarizes common recommendations and improvement areas."""
        recommendations = [stat.recommendations for stat in stats if stat.recommendations]
        return {
            "Top Recommendations": self._get_top_recommendations(recommendations),
            "Priority Areas": self._identify_priority_areas(stats),
        }

    def _get_risk_level(self, score: float) -> str:
        """Determines risk level based on score."""
        if score >= 7:
            return "High Risk"
        elif score >= 4:
            return "Medium Risk"
        return "Low Risk"

    def process_report(self) -> None:
        """
        Processes the report for the company.
        """
        logger.info(f"Processing report for company {self.company_id}")
        try:
            stats, df = self.process_report_data()

            company = Company.objects.get(uuid=self.company_id)
            company_name = company.name

            file_name = (
                f"{company_name}_report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
            )

            self.convert_to_excel(company_name, file_name, stats, df)
            # find report for this company with status=processing and latest
            report = (
                Report.objects.filter(
                    company_id=self.company_id,
                    status=Report.STATUS_PROCESSING,
                )
                .order_by("-created_at")
                .first()
            )

            report.report_file.save(file_name, open(file_name, "rb"))
            report.status = Report.STATUS_PROCESSED
            report.processed = True  # For backwards compatibility
            report.save()

            logger.info(f"Report for company {self.company_id} created")
            os.remove(file_name)
        except Exception as e:
            logger.error(f"Error processing report: {str(e)}")
            Report.objects.filter(
                company_id=self.company_id, status=Report.STATUS_PROCESSING
            ).update(status=Report.STATUS_FAILED)
            raise

    def convert_to_excel(
        self, company_name: str, filename: str, stats: dict, df: pd.DataFrame
    ) -> None:
        """Enhanced Excel report generation with additional worksheets and visualizations."""
        with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
            # Summary sheet
            df.to_excel(
                writer, startrow=0, startcol=0, sheet_name="Detailed Analysis", index=False
            )

            # Create Overview sheet
            overview_df = pd.DataFrame()
            overview_df.to_excel(writer, sheet_name="Executive Summary", startrow=0)

            workbook = writer.book
            overview_sheet = writer.sheets["Executive Summary"]

            # Formatting
            header_format = workbook.add_format(
                {"bold": True, "font_size": 14, "bg_color": "#E6E6E6"}
            )

            # Executive Summary
            row = 0
            overview_sheet.write(
                row, 0, f"Greenwashing Analysis Report - {company_name}", header_format
            )
            row += 2

            # Summary Statistics
            overview_sheet.write(row, 0, "Key Metrics", header_format)
            row += 1
            for key, value in stats["Summary Statistics"].items():
                overview_sheet.write(row, 0, key)
                overview_sheet.write(row, 1, value)
                row += 1

            # Risk Distribution
            row += 2
            overview_sheet.write(row, 0, "Risk Distribution", header_format)
            row += 1
            risk_data = stats["Risk Assessment"]
            for risk_level, data in risk_data.items():
                overview_sheet.write(row, 0, risk_level)
                overview_sheet.write(row, 1, f"{data['percentage']:.1f}%")
                row += 1

            # Category Analysis
            row += 2
            overview_sheet.write(row, 0, "Category Analysis", header_format)
            row += 1
            for category, data in stats["Category Analysis"].items():
                overview_sheet.write(row, 0, category)
                overview_sheet.write(row, 1, f"Avg Score: {data['avg_score']:.1f}")
                overview_sheet.write(row, 2, f"High Risk: {data['high_risk_percentage']:.1f}%")
                row += 1

            # Format detailed analysis sheet
            detailed_sheet = writer.sheets["Detailed Analysis"]
            self._format_detailed_sheet(detailed_sheet, workbook, df)

            # Enhanced Justification Analysis sheet
            justification_df = pd.DataFrame()
            justification_df.to_excel(writer, sheet_name="Justification Analysis", startrow=0)
            justification_sheet = writer.sheets["Justification Analysis"]

            # Formatting
            header_format = workbook.add_format(
                {"bold": True, "font_size": 14, "bg_color": "#E6E6E6"}
            )
            insight_format = workbook.add_format({"bold": True, "font_color": "#1F497D"})

            # Justification Analysis
            row = 0
            justification_sheet.write(row, 0, "Justification Analysis", header_format)
            row += 2

            # Key Insights Section
            justification_sheet.write(row, 0, "Key Insights", insight_format)
            row += 1
            insights = stats["Justification Analysis"]["Key Insights"]

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
            row += 2

            # Evidence Quality
            justification_sheet.write(row, 0, "Evidence Quality", header_format)
            row += 1
            for evidence, count in stats["Justification Analysis"]["Evidence Quality"].items():
                justification_sheet.write(row, 0, evidence)
                justification_sheet.write(row, 1, str(count))
                row += 1

            # Impact Analysis
            row += 2
            justification_sheet.write(row, 0, "Impact Analysis", header_format)
            row += 1
            for impact, count in stats["Justification Analysis"]["Impact Analysis"].items():
                justification_sheet.write(row, 0, impact)
                justification_sheet.write(row, 1, str(count))
                row += 1

            # Time Context
            row += 2
            justification_sheet.write(row, 0, "Time Context", header_format)
            row += 1
            for key, value in stats["Justification Analysis"]["Time Context"].items():
                justification_sheet.write(row, 0, key)
                justification_sheet.write(row, 1, str(value))
                row += 1

            # Consistency
            row += 2
            justification_sheet.write(row, 0, "Consistency", header_format)
            row += 1
            for key, value in stats["Justification Analysis"]["Consistency"].items():
                justification_sheet.write(row, 0, key)
                justification_sheet.write(row, 1, str(value))
                row += 1

            # Add Scoring Rules Explanation sheet
            self._add_scoring_rules_sheet(writer, workbook)

    def _format_detailed_sheet(self, worksheet, workbook, df):
        """Applies enhanced formatting to the detailed analysis worksheet."""
        # Add conditional formatting for risk levels
        red_format = workbook.add_format({"bg_color": "#FFC7CE"})
        yellow_format = workbook.add_format({"bg_color": "#FFEB9C"})
        green_format = workbook.add_format({"bg_color": "#C6EFCE"})

        score_col = df.columns.get_loc("Score")
        worksheet.conditional_format(
            0,
            score_col,
            len(df),
            score_col,
            {"type": "cell", "criteria": ">=", "value": 7, "format": red_format},
        )
        worksheet.conditional_format(
            0,
            score_col,
            len(df),
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
            len(df),
            score_col,
            {"type": "cell", "criteria": "<", "value": 4, "format": green_format},
        )

    def _analyze_justifications(self, stats) -> dict:
        """Analyzes justifications and context data with enhanced metrics."""
        justification_analysis = {
            "Evidence Quality": self._analyze_evidence_justifications(stats),
            "Impact Analysis": self._analyze_impact_justifications(stats),
            "Time Context": self._analyze_time_context(stats),
            "Consistency": self._analyze_consistency(stats),
            "Key Insights": self._generate_justification_insights(stats),  # New insights section
        }
        return justification_analysis

    def _generate_justification_insights(self, stats) -> dict:
        """Generates actionable insights from justification data."""
        insights = {
            "Evidence Quality": {
                "Strongest Evidence": (
                    max(self._analyze_evidence_justifications(stats).items(), key=lambda x: x[1])[
                        0
                    ]
                    if stats
                    else "N/A"
                ),
                "Weakest Evidence": (
                    min(self._analyze_evidence_justifications(stats).items(), key=lambda x: x[1])[
                        0
                    ]
                    if stats
                    else "N/A"
                ),
            },
            "Impact Analysis": {
                "Most Common Impact": (
                    max(self._analyze_impact_justifications(stats).items(), key=lambda x: x[1])[0]
                    if stats
                    else "N/A"
                ),
                "Least Common Impact": (
                    min(self._analyze_impact_justifications(stats).items(), key=lambda x: x[1])[0]
                    if stats
                    else "N/A"
                ),
            },
            "Time Context": {
                "Most Common Confidence Level": (
                    max(
                        self._analyze_time_context(stats)["confidence_levels"].items(),
                        key=lambda x: x[1],
                    )[0]
                    if stats
                    else "N/A"
                )
            },
            "Consistency": {
                "Percentage with Related Claims": (
                    round(
                        self._analyze_consistency(stats)["related_claims_present"]
                        / len(stats)
                        * 100,
                        2,
                    )
                    if stats
                    else 0
                ),
                "Percentage with Analysis": (
                    round(
                        self._analyze_consistency(stats)["analysis_present"] / len(stats) * 100, 2
                    )
                    if stats
                    else 0
                ),
            },
        }
        return insights

    def _analyze_evidence_justifications(self, stats) -> dict:
        """Analyzes evidence justifications."""
        evidence_counts = {}
        for stat in stats:
            evidence = stat.justification.get("evidence", "").lower()
            if evidence:
                if evidence not in evidence_counts:
                    evidence_counts[evidence] = 0
                evidence_counts[evidence] += 1
        return evidence_counts

    def _analyze_impact_justifications(self, stats) -> dict:
        """Analyzes impact justifications."""
        impact_counts = {}
        for stat in stats:
            impact = stat.justification.get("impact", "").lower()
            if impact:
                if impact not in impact_counts:
                    impact_counts[impact] = 0
                impact_counts[impact] += 1
        return impact_counts

    def _analyze_time_context(self, stats) -> dict:
        """Analyzes time context data."""
        time_analysis = {
            "date_present": sum(
                1 for stat in stats if stat.justification.get("time_context", {}).get("date", "")
            ),
            "notes_present": sum(
                1 for stat in stats if stat.justification.get("time_context", {}).get("notes", "")
            ),
            "confidence_levels": {
                "high": sum(
                    1
                    for stat in stats
                    if stat.justification.get("time_context", {}).get("confidence", "").lower()
                    == "high"
                ),
                "medium": sum(
                    1
                    for stat in stats
                    if stat.justification.get("time_context", {}).get("confidence", "").lower()
                    == "medium"
                ),
                "low": sum(
                    1
                    for stat in stats
                    if stat.justification.get("time_context", {}).get("confidence", "").lower()
                    == "low"
                ),
            },
        }
        return time_analysis

    def _analyze_consistency(self, stats) -> dict:
        """Analyzes consistency data."""
        consistency_analysis = {
            "related_claims_present": sum(
                1
                for stat in stats
                if stat.justification.get("consistency", {}).get("related_claims", [])
            ),
            "analysis_present": sum(
                1
                for stat in stats
                if stat.justification.get("consistency", {}).get("analysis", "")
            ),
        }
        return consistency_analysis

    def _get_top_recommendations(self, recommendations: list) -> dict:
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

    def _identify_priority_areas(self, stats) -> dict:
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

    def _add_scoring_rules_sheet(self, writer, workbook):
        """Adds a sheet explaining the scoring rules in human-readable format."""
        # Create new sheet
        rules_df = pd.DataFrame()
        rules_df.to_excel(writer, sheet_name="Scoring Rules", startrow=0)
        rules_sheet = writer.sheets["Scoring Rules"]

        # Formatting
        header_format = workbook.add_format(
            {"bold": True, "font_size": 14, "bg_color": "#E6E6E6"}
        )
        section_format = workbook.add_format(
            {"bold": True, "font_size": 12, "font_color": "#1F497D"}
        )
        text_format = workbook.add_format({"text_wrap": True, "valign": "top"})

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
