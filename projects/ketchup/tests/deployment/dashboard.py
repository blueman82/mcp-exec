"""
Deployment Readiness Dashboard

This module provides a comprehensive dashboard for monitoring deployment
readiness, validation results, and deployment history.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import seaborn as sns
from jinja2 import Template

logger = logging.getLogger(__name__)


class DeploymentDashboard:
    """Dashboard for deployment readiness and monitoring"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent.parent
        self.reports_dir = self.project_root / "tests" / "deployment" / "reports"
        self.dashboard_dir = self.project_root / "tests" / "deployment" / "dashboard"
        self.dashboard_dir.mkdir(exist_ok=True)

        # Set up matplotlib style
        plt.style.use("seaborn-v0_8")
        sns.set_palette("husl")

    def generate_dashboard(self) -> str:
        """Generate comprehensive deployment dashboard"""
        logger.info("Generating deployment readiness dashboard")

        # Collect data
        validation_history = self._load_validation_history()
        rollback_history = self._load_rollback_history()
        monitoring_data = self._load_monitoring_data()
        current_status = self._get_current_status()

        # Generate visualizations
        charts = self._generate_charts(validation_history, rollback_history, monitoring_data)

        # Generate HTML dashboard
        dashboard_html = self._generate_html_dashboard(
            current_status,
            validation_history,
            rollback_history,
            monitoring_data,
            charts,
        )

        # Save dashboard
        dashboard_file = (
            self.dashboard_dir
            / f"deployment_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        )

        with open(dashboard_file, "w") as f:
            f.write(dashboard_html)

        # Also save as latest
        latest_file = self.dashboard_dir / "latest_dashboard.html"
        with open(latest_file, "w") as f:
            f.write(dashboard_html)

        logger.info(f"Dashboard generated: {dashboard_file}")
        return str(dashboard_file)

    def _load_validation_history(self) -> List[Dict]:
        """Load validation history from reports"""
        validation_reports = []

        if not self.reports_dir.exists():
            return validation_reports

        for report_file in self.reports_dir.glob("deployment_readiness_*.txt"):
            try:
                # Parse validation report (simplified)
                with open(report_file) as f:
                    content = f.read()

                # Extract basic info from report text
                timestamp = report_file.stem.split("_")[-2:]  # Extract date and time

                validation_reports.append(
                    {
                        "timestamp": "_".join(timestamp),
                        "file": str(report_file),
                        "status": self._extract_status_from_report(content),
                        "summary": self._extract_summary_from_report(content),
                    }
                )

            except Exception as e:
                logger.warning(f"Failed to parse validation report {report_file}: {e}")

        return sorted(validation_reports, key=lambda x: x["timestamp"], reverse=True)

    def _load_rollback_history(self) -> List[Dict]:
        """Load rollback history"""
        rollback_history = []

        rollback_logs_dir = self.project_root / "tests" / "deployment" / "rollback_logs"

        if not rollback_logs_dir.exists():
            return rollback_history

        for rollback_file in rollback_logs_dir.glob("rollback_*.json"):
            try:
                with open(rollback_file) as f:
                    rollback_data = json.load(f)

                rollback_history.append(rollback_data)

            except Exception as e:
                logger.warning(f"Failed to load rollback log {rollback_file}: {e}")

        return sorted(rollback_history, key=lambda x: x.get("start_time", ""), reverse=True)

    def _load_monitoring_data(self) -> List[Dict]:
        """Load monitoring data"""
        monitoring_data = []

        for monitoring_file in self.reports_dir.glob("monitoring_summary_*.json"):
            try:
                with open(monitoring_file) as f:
                    data = json.load(f)

                monitoring_data.append(data)

            except Exception as e:
                logger.warning(f"Failed to load monitoring data {monitoring_file}: {e}")

        return sorted(monitoring_data, key=lambda x: x.get("start_time", ""), reverse=True)

    def _get_current_status(self) -> Dict:
        """Get current deployment status"""
        return {
            "timestamp": datetime.now().isoformat(),
            "infrastructure_healthy": True,  # Would be determined by checks
            "last_deployment": "v2.342.0",  # Would be fetched from production
            "active_servers": 2,
            "pending_validations": 0,
            "recent_alerts": [],
        }

    def _extract_status_from_report(self, content: str) -> str:
        """Extract overall status from validation report"""
        if "✅ READY" in content:
            return "ready"
        elif "⚠️ READY WITH CONDITIONS" in content:
            return "ready_with_conditions"
        elif "❌ NOT READY" in content:
            return "not_ready"
        elif "🚨 CRITICAL ISSUES" in content:
            return "critical"
        else:
            return "unknown"

    def _extract_summary_from_report(self, content: str) -> Dict:
        """Extract summary statistics from validation report"""
        summary = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "warning_tests": 0,
        }

        # Look for test statistics in the report
        lines = content.split("\n")
        for line in lines:
            if "Total Validations:" in line:
                try:
                    summary["total_tests"] = int(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass
            elif "Passed:" in line and "✅" in line:
                try:
                    summary["passed_tests"] = int(line.split("✅")[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
            elif "Failed:" in line and "❌" in line:
                try:
                    summary["failed_tests"] = int(line.split("❌")[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
            elif "Warnings:" in line and "⚠️" in line:
                try:
                    summary["warning_tests"] = int(line.split("⚠️")[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass

        return summary

    def _generate_charts(
        self,
        validation_history: List[Dict],
        rollback_history: List[Dict],
        monitoring_data: List[Dict],
    ) -> Dict[str, str]:
        """Generate visualization charts"""
        charts = {}

        # Validation trend chart
        if validation_history:
            charts["validation_trend"] = self._create_validation_trend_chart(validation_history)

        # Rollback frequency chart
        if rollback_history:
            charts["rollback_frequency"] = self._create_rollback_frequency_chart(rollback_history)

        # Test results pie chart
        if validation_history:
            charts["test_results_pie"] = self._create_test_results_pie_chart(validation_history)

        # Monitoring overview
        if monitoring_data:
            charts["monitoring_overview"] = self._create_monitoring_overview_chart(monitoring_data)

        return charts

    def _create_validation_trend_chart(self, validation_history: List[Dict]) -> str:
        """Create validation trend chart"""
        fig, ax = plt.subplots(figsize=(12, 6))

        # Prepare data
        dates = []
        statuses = []

        for report in validation_history[-30:]:  # Last 30 reports
            try:
                timestamp = datetime.strptime(report["timestamp"], "%Y%m%d_%H%M%S")
                dates.append(timestamp)

                status_map = {
                    "ready": 4,
                    "ready_with_conditions": 3,
                    "not_ready": 2,
                    "critical": 1,
                    "unknown": 0,
                }
                statuses.append(status_map.get(report["status"], 0))
            except (ValueError, KeyError):
                continue

        if dates and statuses:
            ax.plot(dates, statuses, marker="o", linewidth=2, markersize=6)
            ax.set_ylabel("Deployment Readiness")
            ax.set_xlabel("Date")
            ax.set_title("Deployment Readiness Trend (Last 30 Validations)")

            # Set y-axis labels
            ax.set_yticks([0, 1, 2, 3, 4])
            ax.set_yticklabels(["Unknown", "Critical", "Not Ready", "Ready w/ Conditions", "Ready"])

            plt.xticks(rotation=45)
            plt.tight_layout()

        chart_file = self.dashboard_dir / "validation_trend.png"
        plt.savefig(chart_file, dpi=150, bbox_inches="tight")
        plt.close()

        return str(chart_file)

    def _create_rollback_frequency_chart(self, rollback_history: List[Dict]) -> str:
        """Create rollback frequency chart"""
        fig, ax = plt.subplots(figsize=(10, 6))

        # Group rollbacks by day
        rollback_dates = {}

        for rollback in rollback_history:
            try:
                start_time = datetime.fromisoformat(rollback["start_time"])
                date_key = start_time.date()

                rollback_dates[date_key] = rollback_dates.get(date_key, 0) + 1
            except (ValueError, KeyError):
                continue

        if rollback_dates:
            dates = list(rollback_dates.keys())
            counts = list(rollback_dates.values())

            ax.bar(dates, counts, alpha=0.7)
            ax.set_ylabel("Number of Rollbacks")
            ax.set_xlabel("Date")
            ax.set_title("Rollback Frequency")

            plt.xticks(rotation=45)
            plt.tight_layout()

        chart_file = self.dashboard_dir / "rollback_frequency.png"
        plt.savefig(chart_file, dpi=150, bbox_inches="tight")
        plt.close()

        return str(chart_file)

    def _create_test_results_pie_chart(self, validation_history: List[Dict]) -> str:
        """Create test results pie chart from latest validation"""
        fig, ax = plt.subplots(figsize=(8, 8))

        if validation_history:
            latest = validation_history[0]
            summary = latest.get("summary", {})

            labels = []
            sizes = []
            colors = ["#2ecc71", "#e74c3c", "#f39c12", "#95a5a6"]

            if summary.get("passed_tests", 0) > 0:
                labels.append(f'Passed ({summary["passed_tests"]})')
                sizes.append(summary["passed_tests"])

            if summary.get("failed_tests", 0) > 0:
                labels.append(f'Failed ({summary["failed_tests"]})')
                sizes.append(summary["failed_tests"])

            if summary.get("warning_tests", 0) > 0:
                labels.append(f'Warnings ({summary["warning_tests"]})')
                sizes.append(summary["warning_tests"])

            if labels and sizes:
                ax.pie(
                    sizes,
                    labels=labels,
                    colors=colors[: len(labels)],
                    autopct="%1.1f%%",
                    startangle=90,
                )
                ax.set_title("Latest Validation Results")

        chart_file = self.dashboard_dir / "test_results_pie.png"
        plt.savefig(chart_file, dpi=150, bbox_inches="tight")
        plt.close()

        return str(chart_file)

    def _create_monitoring_overview_chart(self, monitoring_data: List[Dict]) -> str:
        """Create monitoring overview chart"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        if monitoring_data:
            latest_monitoring = monitoring_data[0]

            # Status distribution
            status_counts = latest_monitoring.get("status_counts", {})
            if status_counts:
                statuses = list(status_counts.keys())
                counts = list(status_counts.values())

                ax1.bar(statuses, counts, alpha=0.7)
                ax1.set_title("Monitoring Status Distribution")
                ax1.set_ylabel("Number of Checks")

            # Alerts summary
            alerts_summary = latest_monitoring.get("alerts_summary", {})
            if alerts_summary:
                alert_types = list(alerts_summary.keys())
                alert_counts = list(alerts_summary.values())

                # Truncate long alert names for display
                display_names = [
                    name[:30] + "..." if len(name) > 30 else name for name in alert_types
                ]

                ax2.barh(display_names, alert_counts, alpha=0.7)
                ax2.set_title("Alert Frequency")
                ax2.set_xlabel("Number of Occurrences")

        plt.tight_layout()

        chart_file = self.dashboard_dir / "monitoring_overview.png"
        plt.savefig(chart_file, dpi=150, bbox_inches="tight")
        plt.close()

        return str(chart_file)

    def _generate_html_dashboard(
        self,
        current_status: Dict,
        validation_history: List[Dict],
        rollback_history: List[Dict],
        monitoring_data: List[Dict],
        charts: Dict[str, str],
    ) -> str:
        """Generate HTML dashboard"""

        template_str = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ketchup Deployment Readiness Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
        }
        .subtitle {
            margin: 10px 0 0 0;
            opacity: 0.9;
        }
        .dashboard-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            padding: 20px;
        }
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .card h3 {
            margin-top: 0;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .status-item {
            text-align: center;
            padding: 15px;
            border-radius: 8px;
            color: white;
        }
        .status-ready { background-color: #2ecc71; }
        .status-warning { background-color: #f39c12; }
        .status-error { background-color: #e74c3c; }
        .status-info { background-color: #3498db; }
        .status-item h4 {
            margin: 0 0 5px 0;
            font-size: 1.8em;
        }
        .status-item p {
            margin: 0;
            opacity: 0.9;
        }
        .chart-container {
            text-align: center;
            margin: 20px 0;
        }
        .chart-container img {
            max-width: 100%;
            height: auto;
            border-radius: 4px;
        }
        .history-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        .history-table th,
        .history-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        .history-table th {
            background-color: #f8f9fa;
            font-weight: 600;
        }
        .status-badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: bold;
        }
        .badge-ready { background-color: #d4edda; color: #155724; }
        .badge-warning { background-color: #fff3cd; color: #856404; }
        .badge-error { background-color: #f8d7da; color: #721c24; }
        .badge-critical { background-color: #f5c6cb; color: #721c24; }
        .full-width {
            grid-column: 1 / -1;
        }
        .timestamp {
            color: #666;
            font-size: 0.9em;
            text-align: center;
            margin-top: 20px;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Ketchup Deployment Dashboard</h1>
            <p class="subtitle">Production Readiness Monitoring & Validation</p>
        </div>

        <div class="status-grid">
            <div class="status-item status-{{ 'ready' if current_status.infrastructure_healthy else 'error' }}">
                <h4>{{ '✅' if current_status.infrastructure_healthy else '❌' }}</h4>
                <p>Infrastructure</p>
            </div>
            <div class="status-item status-info">
                <h4>{{ current_status.last_deployment }}</h4>
                <p>Current Version</p>
            </div>
            <div class="status-item status-ready">
                <h4>{{ current_status.active_servers }}</h4>
                <p>Active Servers</p>
            </div>
            <div class="status-item status-{{ 'warning' if current_status.pending_validations > 0 else 'ready' }}">
                <h4>{{ current_status.pending_validations }}</h4>
                <p>Pending Validations</p>
            </div>
        </div>

        <div class="dashboard-grid">
            <div class="card">
                <h3>📊 Validation Trend</h3>
                {% if charts.validation_trend %}
                <div class="chart-container">
                    <img src="{{ charts.validation_trend }}" alt="Validation Trend">
                </div>
                {% else %}
                <p>No validation trend data available.</p>
                {% endif %}
            </div>

            <div class="card">
                <h3>🔄 Latest Test Results</h3>
                {% if charts.test_results_pie %}
                <div class="chart-container">
                    <img src="{{ charts.test_results_pie }}" alt="Test Results">
                </div>
                {% else %}
                <p>No test results data available.</p>
                {% endif %}
            </div>

            <div class="card full-width">
                <h3>📈 Monitoring Overview</h3>
                {% if charts.monitoring_overview %}
                <div class="chart-container">
                    <img src="{{ charts.monitoring_overview }}" alt="Monitoring Overview">
                </div>
                {% else %}
                <p>No monitoring data available.</p>
                {% endif %}
            </div>

            <div class="card">
                <h3>🏥 Recent Validations</h3>
                {% if validation_history %}
                <table class="history-table">
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Status</th>
                            <th>Tests</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for validation in validation_history[:10] %}
                        <tr>
                            <td>{{ validation.timestamp }}</td>
                            <td>
                                <span class="status-badge badge-{{ validation.status.replace('_', '-') }}">
                                    {{ validation.status.replace('_', ' ').title() }}
                                </span>
                            </td>
                            <td>
                                ✅ {{ validation.summary.passed_tests }}
                                ❌ {{ validation.summary.failed_tests }}
                                ⚠️ {{ validation.summary.warning_tests }}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <p>No validation history available.</p>
                {% endif %}
            </div>

            <div class="card">
                <h3>🔙 Rollback History</h3>
                {% if rollback_history %}
                <table class="history-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Version</th>
                            <th>Status</th>
                            <th>Reason</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for rollback in rollback_history[:10] %}
                        <tr>
                            <td>{{ rollback.start_time[:10] if rollback.start_time else 'Unknown' }}</td>
                            <td>{{ rollback.target_version }}</td>
                            <td>
                                <span class="status-badge badge-{{ 'ready' if rollback.status == 'completed' else 'error' }}">
                                    {{ rollback.status.title() }}
                                </span>
                            </td>
                            <td>{{ rollback.reason.replace('_', ' ').title() }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <p>No rollback history available.</p>
                {% endif %}
            </div>
        </div>

        <div class="timestamp">
            Generated on {{ current_status.timestamp[:19] }} |
            <a href="#" onclick="location.reload()">🔄 Refresh</a>
        </div>
    </div>
</body>
</html>
        """

        template = Template(template_str)

        return template.render(
            current_status=current_status,
            validation_history=validation_history,
            rollback_history=rollback_history,
            monitoring_data=monitoring_data,
            charts=charts,
        )


def main():
    """Main entry point for dashboard generation"""
    dashboard = DeploymentDashboard()
    dashboard_file = dashboard.generate_dashboard()

    print(f"Dashboard generated: {dashboard_file}")
    print(f"Open in browser: file://{dashboard_file}")


if __name__ == "__main__":
    main()
