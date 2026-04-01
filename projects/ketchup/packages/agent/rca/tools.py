"""RCA Historian tool definitions for OpenAI function calling."""

RCA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_similar_incidents",
            "description": "Search across ALL Slack channels for similar past incidents using semantic similarity. Use this to find how similar problems were resolved before.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language description of the incident to search for",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_jira_history",
            "description": "Search JIRA for related tickets using JQL. Use this to find past RCA documentation, similar issues, and resolutions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "jql": {
                        "type": "string",
                        "description": "JQL query to search JIRA (e.g., 'project = CPGNCX AND text ~ \"ORA-01555\" ORDER BY created DESC')",
                    }
                },
                "required": ["jql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_instance_health",
            "description": "Query New Relic for instance health metrics using NRQL. Use this to check current or historical system state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nrql": {
                        "type": "string",
                        "description": 'NRQL query (e.g., "SELECT count(*) FROM CampaignHealthCheck SINCE 1 hour ago")',
                    }
                },
                "required": ["nrql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_alerts",
            "description": "Get currently active alert violations from New Relic. Use this to check if there are ongoing infrastructure issues.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]
