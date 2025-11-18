#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequest,
  ListToolsRequest,
  Request,
  Notification,
  Result,
  CallToolRequestSchema,
  ListToolsRequestSchema
} from "@modelcontextprotocol/sdk/types.js";
import { z } from 'zod';
import { zodToJsonSchema } from 'zod-to-json-schema';

import * as search from './operations/search.js';
import * as create from './operations/create.js';
import * as update from './operations/update.js';
import * as auth from './operations/auth.js';
import * as status from './operations/status.js';
import * as getComments from './operations/getComments.js';
import * as addComment from './operations/addComment.js';
import { VERSION } from "./common/version.js";
import { isJiraError } from "./common/errors.js";

const server = new Server(
  {
    name: "corp-jira-mcp-server",
    version: VERSION,
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "test_jira_auth",
        description: "Test authentication with Jira API",
        inputSchema: zodToJsonSchema(auth.AuthTestSchema),
      },
      {
        name: "search_jira_issues",
        description: "Search for Jira issues using JQL (Jira Query Language)",
        inputSchema: zodToJsonSchema(search.JiraSearchSchema),
      },
      {
        name: "create_jira_issue",
        description: "Create a new Jira issue\n\n# Text Formatting Notation Help\n\n## Headings\n\nTo create a header, place `hn.` at the start of the line (where `n` can be a number from 1-6).\n\n```\nh1. Biggest heading\n# Biggest heading  \n\nh2. Bigger heading\n## Bigger heading  \n\nh3. Big heading\n### Big heading  \n\nh4. Normal heading\n#### Normal heading  \n\nh5. Small heading\n##### Small heading  \n\nh6. Smallest heading\n###### Smallest heading  \n```\n\n---\n\n## Text Effects\n\nChange the formatting of words and sentences.\n\n- `*strong*` → **strong**\n- `_emphasis_` → *emphasis*\n- `??citation??` → citation\n- `-deleted-` → ~~deleted~~\n- `+inserted+` → inserted\n- `^superscript^` → superscript\n- `~subscript~` → subscript\n- `{{monospaced}}` → `monospaced`\n\nBlockquote:\n```\nbq. Some block quoted text\n> Some block quoted text\n```\n\nMulti-line quote:\n```\n{quote}\n    here is quotable content\n{quote}\n```\n> here is quotable content  \n\nChange text color:\n```\n{color:red}\nlook ma, red text!\n{color}\n```\n> look ma, red text!\n\n---\n\n## Text Breaks\n\n- Paragraph break: `(empty line)`\n- Line break: `\\`\n- Horizontal ruler: `----`\n- Symbols: `---` → —, `--` → –\n\n---\n\n## Links\n\n- Internal link: `[My Page#anchor]`\n- External link:\n  - `[http://example.com]` → <http://example.com>\n  - `[Text|http://example.com]` → [Text](http://example.com)\n- Email: `[mailto:email@example.com]`\n- File link: `[file:///path/to/file.txt]`\n- Anchor: `{anchor:anchorname}`\n- User link: `[~username]`\n\n---\n\n## Lists\n\n### Bulleted Lists\n```\n* Item 1\n* Item 2\n** Sub-item 2.1\n** Sub-item 2.2\n```\n\n### Numbered Lists\n```\n# Item 1\n# Item 2\n## Sub-item 2.1\n```\n\n### Mixed Lists\n```\n1. Numbered\n    * Nested bullet\n```\n\n---\n\n## Images\n\n```\n!http://example.com/image.png!\n!image.png|thumbnail!\n!image.png|align=right, vspace=4!\n```\n\n---\n\n## Attachments\n\n```\n!media.mov!\n!spaceKey:page^attachment.mov!\n!media.mov|width=300,height=400!\n```\n\n---\n\n## Tables\n\n```\n||Header 1||Header 2||Header 3||\n|Cell 1|Cell 2|Cell 3|\n|Cell 4|Cell 5|Cell 6|\n```\n\n---\n\n## Advanced Formatting\n\nPreformatted text:\n```\n{noformat}\nPreformatted text here\n{noformat}\n```\n\nPanels:\n```\n{panel}\nContent inside a panel\n{panel}\n\n{panel:title=Title|borderStyle=dashed|borderColor=#ccc|bgColor=#fff}\nStyled panel content\n{panel}\n```",
        inputSchema: zodToJsonSchema(create.CreateJiraIssueSchema),
      },
      {
        name: "update_jira_issue",
        description: "Update an existing Jira issue\n\n# Text Formatting Notation Help\n\n## Headings\n\nTo create a header, place `hn.` at the start of the line (where `n` can be a number from 1-6).\n\n```\nh1. Biggest heading\n# Biggest heading  \n\nh2. Bigger heading\n## Bigger heading  \n\nh3. Big heading\n### Big heading  \n\nh4. Normal heading\n#### Normal heading  \n\nh5. Small heading\n##### Small heading  \n\nh6. Smallest heading\n###### Smallest heading  \n```\n\n---\n\n## Text Effects\n\nChange the formatting of words and sentences.\n\n- `*strong*` → **strong**\n- `_emphasis_` → *emphasis*\n- `??citation??` → citation\n- `-deleted-` → ~~deleted~~\n- `+inserted+` → inserted\n- `^superscript^` → superscript\n- `~subscript~` → subscript\n- `{{monospaced}}` → `monospaced`\n\nBlockquote:\n```\nbq. Some block quoted text\n> Some block quoted text\n```\n\nMulti-line quote:\n```\n{quote}\n    here is quotable content\n{quote}\n```\n> here is quotable content  \n\nChange text color:\n```\n{color:red}\nlook ma, red text!\n{color}\n```\n> look ma, red text!\n\n---\n\n## Text Breaks\n\n- Paragraph break: `(empty line)`\n- Line break: `\\`\n- Horizontal ruler: `----`\n- Symbols: `---` → —, `--` → –\n\n---\n\n## Links\n\n- Internal link: `[My Page#anchor]`\n- External link:\n  - `[http://example.com]` → <http://example.com>\n  - `[Text|http://example.com]` → [Text](http://example.com)\n- Email: `[mailto:email@example.com]`\n- File link: `[file:///path/to/file.txt]`\n- Anchor: `{anchor:anchorname}`\n- User link: `[~username]`\n\n---\n\n## Lists\n\n### Bulleted Lists\n```\n* Item 1\n* Item 2\n** Sub-item 2.1\n** Sub-item 2.2\n```\n\n### Numbered Lists\n```\n# Item 1\n# Item 2\n## Sub-item 2.1\n```\n\n### Mixed Lists\n```\n1. Numbered\n    * Nested bullet\n```\n\n---\n\n## Images\n\n```\n!http://example.com/image.png!\n!image.png|thumbnail!\n!image.png|align=right, vspace=4!\n```\n\n---\n\n## Attachments\n\n```\n!media.mov!\n!spaceKey:page^attachment.mov!\n!media.mov|width=300,height=400!\n```\n\n---\n\n## Tables\n\n```\n||Header 1||Header 2||Header 3||\n|Cell 1|Cell 2|Cell 3|\n|Cell 4|Cell 5|Cell 6|\n```\n\n---\n\n## Advanced Formatting\n\nPreformatted text:\n```\n{noformat}\nPreformatted text here\n{noformat}\n```\n\nPanels:\n```\n{panel}\nContent inside a panel\n{panel}\n\n{panel:title=Title|borderStyle=dashed|borderColor=#ccc|bgColor=#fff}\nStyled panel content\n{panel}\n```",
        inputSchema: zodToJsonSchema(update.UpdateJiraIssueSchema),
      },
      {
        name: "get_jira_comments",
        description: "Get comments for a Jira issue",
        inputSchema: zodToJsonSchema(getComments.GetJiraCommentsSchema),
      },
      {
        name: "add_jira_comment",
        description: "Add a comment to a Jira issue",
        inputSchema: zodToJsonSchema(addComment.AddJiraCommentSchema),
      },
      {
        name: "transition_jira_status",
        description: "Transition the status of a Jira issue by applying a transition",
        inputSchema: zodToJsonSchema(status.TransitionJiraStatusSchema),
      },
      {
        name: "get_jira_transitions",
        description: "Get available transitions for a Jira issue",
        inputSchema: zodToJsonSchema(z.object({ issueIdOrKey: z.string() })),
      },
      {
        name: "transition_jira_status_by_name",
        description: "Transition the status of a Jira issue by specifying the target status name",
        inputSchema: zodToJsonSchema(z.object({
          issueIdOrKey: z.string(),
          statusName: z.string(),
          comment: z.string().optional(),
          resolution: z.object({ name: z.string() }).optional(),
          fields: z.record(z.any()).optional()
        })),
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  try {
    if (!request.params.arguments) {
      throw new Error("Arguments are required");
    }

    switch (request.params.name) {
      case "test_jira_auth": {
        const result = await auth.testAuth();
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      case "search_jira_issues": {
        const args = search.JiraSearchSchema.parse(request.params.arguments);
        const results = await search.searchJiraIssues(args);
        return {
          content: [{ type: "text", text: JSON.stringify(results, null, 2) }],
        };
      }

      case "create_jira_issue": {
        const args = create.CreateJiraIssueSchema.parse(request.params.arguments);
        
        try {
          const result = await create.createJiraIssue(args);
          
          if (result && typeof result === 'object' && 'success' in result && !result.success) {
            throw new Error('Failed to create issue');
          }
          
          return {
            content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
          };
        } catch (error) {
          console.error('Create Jira Issue Error:', error);
          throw error;
        }
      }

      case "update_jira_issue": {
        const args = update.UpdateJiraIssueSchema.parse(request.params.arguments);
        const result = await update.updateJiraIssue(args);
        
        if (result && typeof result === 'object' && 'success' in result && !result.success) {
          throw new Error('Failed to update issue');
        }
        
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      case "get_jira_comments": {
        const args = getComments.GetJiraCommentsSchema.parse(request.params.arguments);
        const result = await getComments.getJiraComments(args);
        
        if (result && typeof result === 'object' && 'success' in result && !result.success) {
          throw new Error('Failed to get issue comments');
        }
        
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      case "add_jira_comment": {
        const args = addComment.AddJiraCommentSchema.parse(request.params.arguments);
        const result = await addComment.addJiraComment(args);
        
        if (result && typeof result === 'object' && 'success' in result && !result.success) {
          throw new Error('Failed to add comment to issue');
        }
        
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      case "transition_jira_status": {
        const args = status.TransitionJiraStatusSchema.parse(request.params.arguments);
        const result = await status.transitionJiraStatus(args);
        
        if (result && typeof result === 'object' && 'success' in result && !result.success) {
          throw new Error('Failed to transition issue status');
        }
        
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      case "transition_jira_status_by_name": {
        const { issueIdOrKey, statusName, comment, resolution, fields } = z.object({
          issueIdOrKey: z.string(),
          statusName: z.string(),
          comment: z.string().optional(),
          resolution: z.object({ name: z.string() }).optional(),
          fields: z.record(z.any()).optional()
        }).parse(request.params.arguments);
        
        const result = await status.transitionJiraStatusByName(
          issueIdOrKey,
          statusName,
          comment,
          resolution,
          fields
        );
        
        if (result && typeof result === 'object' && 'success' in result && !result.success) {
          throw new Error('Failed to transition issue status by name');
        }
        
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      case "get_jira_transitions": {
        const { issueIdOrKey } = z.object({ issueIdOrKey: z.string() }).parse(request.params.arguments);
        const result = await status.getJiraTransitions(issueIdOrKey);
        
        if (result && typeof result === 'object' && 'success' in result && !result.success) {
          throw new Error('Failed to get issue transitions');
        }
        
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      default:
        throw new Error(`Unknown tool: ${request.params.name}`);
    }
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new Error(`Invalid input: ${JSON.stringify(error.errors)}`);
    }
    if (isJiraError(error)) {
      throw new Error(`Jira API error: ${error.message}`);
    }
    throw error;
  }
});

async function runServer() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  process.stderr.write("Corporate Jira MCP Server running on stdio\n");
}

runServer().catch((error) => {
  console.error("Fatal error in main():", error);
  process.exit(1);
});
