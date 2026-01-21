# Live State Removal Refactor - January 2026

## Summary
Removed all live state metrics from quarterly dashboard reports. Reports now show only historical data (data at time of generation).

## Removed Metrics
- "Overall CSO Coverage: 100%" (always 100%, pointless)
- "Currently Active CSO Channels: X" (live state)
- "Archived CSO Channels: Y" (live state)
- Product coverage percentages (confusing)
- CSO Coverage Per Product section with CAMPAIGN_PERCENTAGE, AJO_PERCENTAGE

## New Metrics
- "CSO Channels Tracked: X" with breakdown "Y Campaign, Z AJO, W Other"
- "Other" category for channels with missing/unknown product type (35 in DB)

## Files Deleted
- packages/slack/models/cso_metrics.py (CSOMetrics, CSOChannelCounts dataclasses)
- tests/unit/test_cso_metrics_models.py
- tests/unit/test_html_generator_cso_cards.py
- tests/unit/test_metrics_data_collector_cso_split.py

## Files Modified
1. packages/slack/services/metrics_data_collector.py
   - Removed _split_active_vs_archived() method
   - Removed _calculate_overall_coverage() method
   - Updated _calculate_product_coverage() to return {campaign, ajo, other, total}
   - Updated collect_cso_metrics() to return product_counts instead of old structure
   - Updated _get_empty_cso_metrics()

2. packages/core/exports/html_generator.py
   - Updated _inject_cso_values() to use product_counts
   - Updated HTML template: removed old cards, added new CSO_BREAKDOWN

## Key Principle
Quarterly reports show data at time of generation. If run tomorrow with new archives, numbers change - that's expected and correct.
