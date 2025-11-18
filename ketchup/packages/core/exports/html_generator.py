"""
html_generator.py

Generates HTML dashboard from metrics data.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from packages.core.exports.time_period_formatter import (
    format_date_range,
    format_time_period_full,
    format_time_period_label,
)
from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class MetricsHTMLGenerator:
    """
    Generates HTML dashboard from metrics data.

    Adapts CSV generator pattern for HTML output with embedded template.
    """

    def __init__(self):
        """Initialize MetricsHTMLGenerator."""
        logger.info("MetricsHTMLGenerator initialized")

    def generate(
        self,
        cso_metrics: Dict[str, Any],
        technical_metrics: Dict[str, Any],
        jira_metrics: Dict[str, Any],
        period_type: str = "7_days",
        month: int = None,
        quarter: int = None,
        year: int = None,
        is_partial: bool = False,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> str:
        """
        Generate HTML dashboard with metrics.

        Args:
            cso_metrics: Executive CSO metrics
            technical_metrics: Technical system health metrics
            jira_metrics: JIRA posting metrics
            period_type: Time period type
            month: Month number for monthly
            quarter: Quarter number for quarterly
            year: Year
            is_partial: Is ongoing period
            start_date: Start datetime
            end_date: End datetime

        Returns:
            Complete HTML document string
        """
        logger.info(f"Generating HTML dashboard (period: {period_type})")

        html = self._get_html_template()

        # Inject time period labels
        html = self._inject_time_period_values(
            html, period_type, month, quarter, year, is_partial, start_date, end_date
        )

        # Inject metrics (existing)
        html = self._inject_cso_values(html, cso_metrics)
        html = self._inject_technical_values(html, technical_metrics)
        html = self._inject_jira_values(html, jira_metrics)

        # Inject timestamp
        html = html.replace(
            "{{TIMESTAMP}}",
            datetime.now(timezone.utc).strftime("%B %d, %Y %H:%M:%S UTC"),
        )

        return html

    async def generate_html(self, metrics_data: Dict[str, Any]) -> str:
        """
        Generate HTML dashboard from metrics.

        Args:
            metrics_data: Combined CSO + technical metrics

        Returns:
            Complete HTML document as string
        """
        try:
            cso = metrics_data.get("cso", {})
            tech = metrics_data.get("technical", {})

            timestamp = datetime.now(timezone.utc).strftime("%B %d, %Y %H:%M:%S UTC")

            html = self._get_html_template()
            html = self._inject_values(html, cso, tech, timestamp)

            logger.info("HTML dashboard generated successfully")
            return html

        except Exception as e:
            logger.error(f"Error generating HTML: {e}", exc_info=True)
            return self._get_error_html()

    def _inject_values(
        self, html: str, cso: Dict[str, Any], tech: Dict[str, Any], timestamp: str
    ) -> str:
        """Inject metric values into HTML template."""
        html = html.replace("{{TIMESTAMP}}", timestamp)
        html = self._inject_cso_values(html, cso)
        html = self._inject_technical_values(html, tech)

        # Inject JIRA posting metrics
        jira = cso.get("jira_posting", {})
        html = self._inject_jira_values(html, jira)

        return html

    def _inject_cso_values(self, html: str, cso: Dict[str, Any]) -> str:
        """Inject CSO metric values."""
        html = html.replace(
            "{{PRODUCTS_COUNT}}", str(len(cso.get("products_using_ketchup", [])))
        )
        html = html.replace(
            "{{OVERALL_COVERAGE}}", f"{cso.get('overall_cso_coverage', 0)}%"
        )

        # Use consistent counts from product_coverage, not active_cso_channels
        product_coverage = cso.get("product_coverage", {})
        cso_with_tracking = sum(p.get("channels", 0) for p in product_coverage.values())
        total_monitored = sum(p.get("total", 0) for p in product_coverage.values())

        html = html.replace(
            "{{CSO_DETAIL}}",
            f"{cso_with_tracking} of {total_monitored} channels with CSO tracking",
        )

        html = html.replace(
            "{{AUTO_NOTIFICATION_DELIVERY}}",
            f"{cso.get('auto_notification_delivery', 0)}%",
        )

        campaign = product_coverage.get("campaign", {})
        html = html.replace(
            "{{CAMPAIGN_PERCENTAGE}}", str(campaign.get("percentage", 0))
        )
        html = html.replace(
            "{{CAMPAIGN_DETAIL}}",
            f"{campaign.get('channels', 0)} of " f"{campaign.get('total', 0)} channels",
        )

        ajo = product_coverage.get("ajo", {})
        html = html.replace("{{AJO_PERCENTAGE}}", str(ajo.get("percentage", 0)))
        html = html.replace(
            "{{AJO_DETAIL}}",
            f"{ajo.get('channels', 0)} of {ajo.get('total', 0)} channels",
        )

        # Handle CSOMetrics dataclass for active vs archived split
        cso_metrics = cso.get("cso_metrics")
        if cso_metrics and hasattr(cso_metrics, "currently_active"):
            # Extract values from CSOMetrics dataclass
            currently_active = cso_metrics.currently_active
            archived = cso_metrics.archived

            # Currently Active card values
            html = html.replace(
                "{{CURRENTLY_ACTIVE_TOTAL}}", str(currently_active.total)
            )
            html = html.replace(
                "{{CURRENTLY_ACTIVE_BREAKDOWN}}",
                f"{currently_active.campaign} Campaign, {currently_active.ajo} AJO",
            )

            # Archived card values
            html = html.replace("{{ARCHIVED_TOTAL}}", str(archived.total))
            html = html.replace(
                "{{ARCHIVED_BREAKDOWN}}",
                f"{archived.campaign} Campaign, {archived.ajo} AJO",
            )
        else:
            # Backward compatibility - use old active_cso_channels if cso_metrics not available
            html = html.replace(
                "{{CURRENTLY_ACTIVE_TOTAL}}", str(cso.get("active_cso_channels", 0))
            )
            html = html.replace("{{CURRENTLY_ACTIVE_BREAKDOWN}}", "N/A")
            html = html.replace("{{ARCHIVED_TOTAL}}", "0")
            html = html.replace("{{ARCHIVED_BREAKDOWN}}", "0 Campaign, 0 AJO")

        return html

    def _inject_jira_values(self, html: str, jira: Dict[str, Any]) -> str:
        """Inject JIRA posting metric values."""
        html = html.replace("{{JIRA_POSTING_RATE}}", f"{jira.get('total_coverage', 0)}")
        html = html.replace(
            "{{CHANNELS_WITH_REPORTS}}", str(jira.get("channels_with_reports", 0))
        )
        html = html.replace(
            "{{TOTAL_JIRA_CHANNELS}}", str(jira.get("total_channels", 0))
        )

        # Technical breakdown details
        details = jira.get("posting_details", {})
        primary_only = details.get("primary_only", 0)
        csopm_only = details.get("csopm_only", 0)
        both = details.get("both_tickets", 0)

        html = html.replace("{{PRIMARY_POSTED}}", str(primary_only + both))
        html = html.replace("{{CSOPM_POSTED}}", str(csopm_only + both))
        html = html.replace("{{BOTH_POSTED}}", str(both))
        html = html.replace(
            "{{FAILED_NO_TICKET}}", str(details.get("no_valid_ticket", 0))
        )
        html = html.replace(
            "{{API_FAILURES_PENDING}}",
            str(details.get("api_failures", 0) + details.get("pending", 0)),
        )
        return html

    def _inject_technical_values(self, html: str, tech: Dict[str, Any]) -> str:
        """Inject technical metric values."""
        # Status update metrics
        public_updates = tech.get("public_updates", {})
        total_posts = public_updates.get("total_posts")
        channels_with_updates = public_updates.get("channels_with_updates", 0)

        # Inject total posts (show if available)
        if total_posts is not None:
            html = html.replace("{{TOTAL_POSTS}}", str(total_posts))
        else:
            html = html.replace("{{TOTAL_POSTS}}", "N/A")

        html = html.replace("{{UPDATES_POSTED}}", str(channels_with_updates))
        html = html.replace(
            "{{SUCCESS_RATE}}", f"{public_updates.get('success_rate', 0)}"
        )

        war_room_msg = tech.get("war_room_messages", {})
        unique_per_channel = war_room_msg.get("unique_users_per_channel", 0)
        total_sent = war_room_msg.get("total_sent", 0)
        html = html.replace("{{PEOPLE_JOINED}}", str(unique_per_channel))
        html = html.replace(
            "{{MESSAGE_DELIVERY_RATE}}", f"{war_room_msg.get('delivery_rate', 0)}"
        )
        html = html.replace("{{TOTAL_MESSAGES}}", f"{total_sent:,}")
        html = html.replace(
            "{{NOTIFICATION_DETAIL}}",
            f"{unique_per_channel} user joins ({total_sent} total notifications)",
        )

        system_health = tech.get("system_health", {})
        html = html.replace(
            "{{RECENTLY_ARCHIVED}}", str(system_health.get("recently_archived", 0))
        )

        return html

    def _inject_time_period_values(
        self,
        html: str,
        period_type: str,
        month: int,
        quarter: int,
        year: int,
        is_partial: bool,
        start_date: datetime,
        end_date: datetime,
    ) -> str:
        """
        Inject time period labels into template.

        Args:
            html: HTML template
            period_type: Time period type
            month: Month number
            quarter: Quarter number
            year: Year
            is_partial: Is partial period
            start_date: Start datetime
            end_date: End datetime

        Returns:
            HTML with time period values injected
        """
        # Generate labels
        period_label = format_time_period_label(period_type, month, quarter, year)
        period_full = format_time_period_full(
            period_type, month, quarter, year, is_partial
        )
        date_range = format_date_range(start_date, end_date)

        # Inject
        html = html.replace("{{PERIOD_LABEL}}", period_label)
        html = html.replace("{{PERIOD_FULL}}", period_full)
        html = html.replace("{{DATE_RANGE}}", date_range)

        return html

    def _get_html_template(self) -> str:
        """Get HTML template with placeholder markers."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ketchup Performance Dashboard</title>
    <style>
        :root {
            /* Light theme (default) */
            --bg-primary: #f5f5f5;
            --bg-secondary: white;
            --bg-card: #f8f9fa;
            --text-primary: #333;
            --text-secondary: #7f8c8d;
            --text-muted: #95a5a6;
            --border-color: #e1e8ed;
            --border-light: #ecf0f1;
            --shadow: rgba(0,0,0,0.1);
            --header-bg-start: #2c3e50;
            --header-bg-end: #34495e;
            --header-text: white;
        }
        
        [data-theme="dark"] {
            --bg-primary: #1a1a1a;
            --bg-secondary: #2d2d2d;
            --bg-card: #3a3a3a;
            --text-primary: #e0e0e0;
            --text-secondary: #b0b0b0;
            --text-muted: #888;
            --border-color: #4a4a4a;
            --border-light: #3a3a3a;
            --shadow: rgba(0,0,0,0.3);
            --header-bg-start: #1e2936;
            --header-bg-end: #2c3845;
            --header-text: #e0e0e0;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            line-height: 1.6;
            color: var(--text-primary);
            background: var(--bg-primary);
            padding: 20px;
            transition: background 0.3s ease, color 0.3s ease;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: var(--bg-secondary);
            border-radius: 12px;
            box-shadow: 0 2px 8px var(--shadow);
            transition: background 0.3s ease, box-shadow 0.3s ease;
        }
        .header {
            background: linear-gradient(135deg, var(--header-bg-start) 0%, var(--header-bg-end) 100%);
            color: var(--header-text);
            padding: 30px;
            text-align: center;
            position: relative;
        }
        .theme-toggle {
            position: absolute;
            top: 20px;
            right: 30px;
            background: rgba(255,255,255,0.15);
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 50px;
            padding: 8px 16px;
            cursor: pointer;
            font-size: 18px;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .theme-toggle:hover {
            background: rgba(255,255,255,0.25);
            transform: scale(1.05);
        }
        .header h1 { font-size: 32px; font-weight: 600; margin-bottom: 10px; }
        .header .subtitle { font-size: 16px; opacity: 0.9; }
        .reporting-period {
            font-size: 14px;
            color: var(--header-text);
            margin: 8px 0;
            font-weight: 500;
            opacity: 0.9;
        }
        .header .meta { margin-top: 15px; font-size: 14px; opacity: 0.8; }
        .content { padding: 40px; }
        .section { margin-bottom: 40px; }
        .section-header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #3498db;
        }
        .section-header .icon { font-size: 32px; margin-right: 15px; }
        .section-header h2 { color: var(--text-primary); font-size: 24px; font-weight: 600; }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .metric-card {
            background: var(--bg-card);
            border-radius: 8px;
            padding: 20px;
            border-left: 4px solid #3498db;
            transition: background 0.3s ease;
        }
        .metric-card.success { border-left-color: #27ae60; }
        .metric-card.info { border-left-color: #3498db; }
        .metric-label {
            font-size: 14px;
            color: var(--text-secondary);
            margin-bottom: 8px;
            text-transform: uppercase;
        }
        .metric-value {
            font-size: 36px;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 5px;
        }
        .metric-detail { font-size: 13px; color: var(--text-muted); }
        .product-breakdown {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            transition: background 0.3s ease, border-color 0.3s ease;
        }
        .product-item {
            padding: 15px 0;
            border-bottom: 1px solid var(--border-light);
        }
        .product-item:last-child { border-bottom: none; }
        .product-name { font-weight: 600; color: var(--text-primary); font-size: 16px; }
        .coverage-percentage {
            font-weight: 700;
            color: #27ae60;
            font-size: 18px;
        }
        .technical-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
        }
        .technical-card {
            background: var(--bg-secondary);
            border: 2px solid var(--border-color);
            border-radius: 8px;
            padding: 25px;
            transition: background 0.3s ease, border-color 0.3s ease;
        }
        .technical-card h3 { color: var(--text-primary); font-size: 18px; margin-bottom: 15px; }
        .stat-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid var(--border-light);
        }
        .stat-row:last-child { border-bottom: none; }
        .stat-label { 
            color: var(--text-secondary); 
            font-size: 14px;
            position: relative;
            display: inline-flex;
            align-items: center;
        }
        .stat-value { font-weight: 600; color: var(--text-primary); font-size: 16px; }
        .stat-value.success { color: #27ae60; }
        .tooltip {
            position: relative;
            display: inline-block;
            margin-left: 6px;
        }
        .tooltip-icon {
            display: inline-block;
            width: 16px;
            height: 16px;
            background: var(--text-secondary);
            color: var(--bg-secondary);
            border-radius: 50%;
            text-align: center;
            font-size: 11px;
            line-height: 16px;
            cursor: help;
            font-weight: bold;
        }
        .tooltip-text {
            visibility: hidden;
            width: 280px;
            background: var(--text-primary);
            color: var(--bg-secondary);
            text-align: left;
            border-radius: 6px;
            padding: 10px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            margin-left: -140px;
            opacity: 0;
            transition: opacity 0.3s;
            font-size: 12px;
            line-height: 1.4;
            box-shadow: 0 4px 12px var(--shadow);
        }
        .tooltip-text::after {
            content: "";
            position: absolute;
            top: 100%;
            left: 50%;
            margin-left: -5px;
            border-width: 5px;
            border-style: solid;
            border-color: var(--text-primary) transparent transparent transparent;
        }
        .tooltip:hover .tooltip-text {
            visibility: visible;
            opacity: 1;
        }
        .footer {
            background: var(--bg-card);
            padding: 20px 40px;
            text-align: center;
            color: var(--text-secondary);
            font-size: 13px;
            border-top: 1px solid var(--border-color);
            transition: background 0.3s ease, border-color 0.3s ease;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <button class="theme-toggle" onclick="toggleTheme()" aria-label="Toggle theme">
                <span id="theme-icon">☀️</span>
                <span id="theme-text">Light</span>
            </button>
            <h1>🎯 Ketchup Performance Dashboard - {{PERIOD_LABEL}}</h1>
            <div class="reporting-period">
                📅 Reporting Period: {{PERIOD_FULL}} ({{DATE_RANGE}})
            </div>
            <div class="meta">Generated: {{TIMESTAMP}}</div>
        </div>

        <div class="content">
            <div class="section">
                <div class="section-header">
                    <div class="icon">🎯</div>
                    <h2>Executive CSO Management Overview</h2>
                </div>

                <div class="metrics-grid">
                    <div class="metric-card success">
                        <div class="metric-label">Products Using Ketchup</div>
                        <div class="metric-value">{{PRODUCTS_COUNT}}</div>
                        <div class="metric-detail">Adobe Campaign & AJO</div>
                    </div>
                    <div class="metric-card success">
                        <div class="metric-label">Overall CSO Coverage</div>
                        <div class="metric-value">{{OVERALL_COVERAGE}}</div>
                        <div class="metric-detail">{{CSO_DETAIL}}</div>
                    </div>

                    <div class="metric-card success">
                        <div class="metric-label">Auto-Notification Delivery</div>
                        <div class="metric-value">{{AUTO_NOTIFICATION_DELIVERY}}</div>
                        <div class="metric-detail">{{NOTIFICATION_DETAIL}} successfully</div>
                    </div>
                </div>

                <h3 style="color: var(--text-primary); margin-bottom: 15px;">📊 CSO Coverage Per Product</h3>
                <div class="product-breakdown">
                    <div class="product-item">
                        <div class="product-name">Adobe Campaign</div>
                        <div class="coverage-percentage">{{CAMPAIGN_PERCENTAGE}}%</div>
                        <div class="metric-detail">{{CAMPAIGN_DETAIL}}</div>
                    </div>
                    <div class="product-item">
                        <div class="product-name">Adobe Journey Optimizer</div>
                        <div class="coverage-percentage">{{AJO_PERCENTAGE}}%</div>
                        <div class="metric-detail">{{AJO_DETAIL}}</div>
                    </div>
                </div>

                <div class="metrics-grid">
                    <div class="metric-card success">
                        <div class="metric-label">Currently Active CSO Channels</div>
                        <div class="metric-value">{{CURRENTLY_ACTIVE_TOTAL}}</div>
                        <div class="metric-detail">{{CURRENTLY_ACTIVE_BREAKDOWN}}</div>
                    </div>
                    <div class="metric-card info">
                        <div class="metric-label">Archived CSO Channels</div>
                        <div class="metric-value">{{ARCHIVED_TOTAL}}</div>
                        <div class="metric-detail">{{ARCHIVED_BREAKDOWN}}</div>
                    </div>
                    <div class="metric-card info">
                        <div class="metric-label">JIRA Reports Posted</div>
                        <div class="metric-value">{{JIRA_POSTING_RATE}}%</div>
                        <div class="metric-detail">{{CHANNELS_WITH_REPORTS}} of {{TOTAL_JIRA_CHANNELS}} channels</div>
                    </div>
                </div>
            </div>

            <div class="section">
                <div class="section-header">
                    <div class="icon">📋</div>
                    <h2>Technical System Health</h2>
                </div>

                <div class="technical-grid">
                    <div class="technical-card">
                        <h3>✅ Public Status Updates</h3>
                        <div class="stat-row">
                            <span class="stat-label">Posts Created</span>
                            <span class="stat-value">{{TOTAL_POSTS}}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Active Channels</span>
                            <span class="stat-value">{{UPDATES_POSTED}}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Success Rate</span>
                            <span class="stat-value success">{{SUCCESS_RATE}}%</span>
                        </div>
                    </div>

                    <div class="technical-card">
                        <h3>💬 War Room Auto-Messages</h3>
                        <div class="stat-row">
                            <span class="stat-label">
                                User Joins Tracked
                                <span class="tooltip">
                                    <span class="tooltip-icon">?</span>
                                    <span class="tooltip-text">
                                        Unique users per channel, summed across all channels. A user joining multiple channels is counted once per channel. Can be higher than total notifications when multiple users join simultaneously.
                                    </span>
                                </span>
                            </span>
                            <span class="stat-value">{{PEOPLE_JOINED}}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Delivery Rate</span>
                            <span class="stat-value success">{{MESSAGE_DELIVERY_RATE}}%</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Total Notifications</span>
                            <span class="stat-value">{{TOTAL_MESSAGES}}</span>
                        </div>
                    </div>



                    <div class="technical-card">
                        <h3>📋 JIRA Posting Breakdown</h3>
                        <div class="stat-row">
                            <span class="stat-label">Posted to Primary Ticket</span>
                            <span class="stat-value">{{PRIMARY_POSTED}}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Posted to CSOPM Ticket</span>
                            <span class="stat-value">{{CSOPM_POSTED}}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Posted to Both</span>
                            <span class="stat-value success">{{BOTH_POSTED}}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Failed (No Ticket Found)</span>
                            <span class="stat-value">{{FAILED_NO_TICKET}}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">API Failures / Pending</span>
                            <span class="stat-value">{{API_FAILURES_PENDING}}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="footer">
            <p><strong>Ketchup Performance Dashboard</strong> • Generated: {{TIMESTAMP}}</p>
        </div>
    </div>
    
    <script>
        // Theme toggle functionality with localStorage persistence
        function toggleTheme() {
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            
            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('dashboard-theme', newTheme);
            updateThemeButton(newTheme);
        }
        
        function updateThemeButton(theme) {
            const icon = document.getElementById('theme-icon');
            const text = document.getElementById('theme-text');
            
            if (theme === 'dark') {
                icon.textContent = '🌙';
                text.textContent = 'Dark';
            } else {
                icon.textContent = '☀️';
                text.textContent = 'Light';
            }
        }
        
        // Load saved theme on page load
        (function() {
            const savedTheme = localStorage.getItem('dashboard-theme') || 'light';
            document.documentElement.setAttribute('data-theme', savedTheme);
            updateThemeButton(savedTheme);
        })();
    </script>
</body>
</html>"""

    def _get_error_html(self) -> str:
        """Return error HTML when generation fails."""
        return """<!DOCTYPE html>
<html><head><title>Error</title></head>
<body><h1>Error generating metrics dashboard</h1>
<p>Please try again later.</p></body></html>"""
