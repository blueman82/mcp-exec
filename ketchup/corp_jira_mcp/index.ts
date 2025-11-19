#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import express from 'express';
import { createServer } from 'http';
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
import * as getFields from './operations/getFields.js';
import * as revokePAT from './operations/revokePAT.js';
import * as validatePAT from './operations/validatePAT.js';
import { VERSION } from "./common/version.js";
import { isJiraError } from "./common/errors.js";
import { setCurrentAuthToken } from "./common/utils.js";

/**
 * Middleware to extract Authorization header from incoming requests
 * This is called automatically for each MCP request when our Python client
 * makes HTTP requests to the MCP server.
 */
function extractAuthorizationHeader(request: any): void {
  // Extract Authorization header from the incoming request
  const authHeader = request.headers?.authorization || request.headers?.Authorization;
  
  // Set the token for the current request
  setCurrentAuthToken(authHeader);
  
  // Log for debugging
  if (authHeader) {
    console.error('Authorization header extracted from request');
  } else {
    console.error('No Authorization header found in request');
  }
}

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
        description: "Create a new Jira issue",
        inputSchema: zodToJsonSchema(create.CreateJiraIssueSchema),
      },
      {
        name: "update_jira_issue",
        description: "Update an existing Jira issue",
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
      {
        name: "get_jira_fields",
        description: "Get all available Jira fields including custom fields",
        inputSchema: zodToJsonSchema(getFields.GetFieldsSchema),
      },
      {
        name: "revoke_pat",
        description: "Revoke (delete) a JIRA Personal Access Token (PAT) by token ID",
        inputSchema: zodToJsonSchema(revokePAT.RevokePATSchema),
      },
      {
        name: "validate_pat",
        description: "Validate a PAT token by testing authentication with Jira API",
        inputSchema: zodToJsonSchema(validatePAT.ValidatePATSchema),
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  try {
    // Extract Authorization header for each request
    extractAuthorizationHeader(request);

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

      case "get_jira_fields": {
        const result = await getFields.getJiraFields();
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      case "revoke_pat": {
        const args = revokePAT.RevokePATSchema.parse(request.params.arguments);
        const result = await revokePAT.revokePAT(args);

        if (result && typeof result === 'object' && 'success' in result && !result.success) {
          throw new Error('Failed to revoke PAT');
        }

        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }

      case "validate_pat": {
        const args = validatePAT.ValidatePATSchema.parse(request.params.arguments);
        const result = await validatePAT.validatePAT(args);

        if (result && typeof result === 'object' && 'success' in result && !result.success) {
          throw new Error('Failed to validate PAT');
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
  const port = parseInt(process.env.PORT || '8081', 10);
  const app = express();
  const httpServer = createServer(app);

  app.use(express.json());

  // Store active transports by session ID
  const activeTransports = new Map<string, SSEServerTransport>();

  // Health check endpoint
  app.get('/health', (req, res) => {
    res.json({ status: 'ok' });
  });

  // MCP SSE endpoint for establishing the event stream
  app.get('/sse', async (req, res) => {
    try {
      const transport = new SSEServerTransport('/message', res);
      
      // Store the transport for message routing
      activeTransports.set(transport.sessionId, transport);
      
      // Set up cleanup when connection closes
      transport.onclose = () => {
        activeTransports.delete(transport.sessionId);
        process.stderr.write(`SSE connection closed for session: ${transport.sessionId}\n`);
      };

      transport.onerror = (error: Error) => {
        process.stderr.write(`SSE transport error for session ${transport.sessionId}: ${error.message}\n`);
        activeTransports.delete(transport.sessionId);
      };

      // Connect the MCP server to this transport
      await server.connect(transport);
      await transport.start();
      
      process.stderr.write(`New SSE connection established: ${transport.sessionId}\n`);
      // Don't send any response here - SSEServerTransport manages the response
    } catch (error) {
      process.stderr.write(`Failed to establish SSE connection: ${error}\n`);
      // Only send error response if headers haven't been sent
      if (!res.headersSent) {
        res.status(500).json({ error: 'Failed to establish SSE connection' });
      }
    }
  });

  // MCP message endpoint for receiving JSON-RPC messages
  app.post('/message', async (req, res) => {
    try {
      // For direct tool calls, create a temporary transport
      if (req.body && req.body.method === 'tools/call') {
        return await handleDirectToolCall(req, res);
      }
      
      // Extract session ID from request headers or body
      const sessionId = req.headers['x-session-id'] as string || req.body.sessionId;
      
      if (!sessionId) {
        return res.status(400).json({ error: 'Session ID required' });
      }

      const transport = activeTransports.get(sessionId);
      if (!transport) {
        return res.status(404).json({ error: 'Session not found' });
      }

      // Handle the incoming message through the MCP transport
      await transport.handlePostMessage(req, res, req.body);
      
    } catch (error) {
      process.stderr.write(`Error handling message: ${error}\n`);
      res.status(500).json({ error: 'Failed to process message' });
    }
  });

  // Helper function to handle direct tool calls without SSE session
  async function handleDirectToolCall(req: any, res: any) {
    try {
      // Extract Authorization header for dynamic token injection
      const authHeader = req.headers.authorization;
      if (authHeader) {
        setCurrentAuthToken(authHeader);
      }

      const request = req.body;
      if (!request.params || !request.params.arguments) {
        return res.status(400).json({
          jsonrpc: '2.0',
          id: request.id,
          error: { code: -32602, message: 'Arguments are required' }
        });
      }

      let result;
      switch (request.params.name) {
        case 'test_jira_auth': {
          const authResult = await auth.testAuth();
          result = {
            content: [{ type: 'text', text: JSON.stringify(authResult, null, 2) }]
          };
          break;
        }
        
        case 'search_jira_issues': {
          const args = search.JiraSearchSchema.parse(request.params.arguments);
          const searchResult = await search.searchJiraIssues(args);
          result = {
            content: [{ type: 'text', text: JSON.stringify(searchResult, null, 2) }]
          };
          break;
        }
        
        case 'get_jira_comments': {
          const args = getComments.GetJiraCommentsSchema.parse(request.params.arguments);
          const commentsResult = await getComments.getJiraComments(args);
          result = {
            content: [{ type: 'text', text: JSON.stringify(commentsResult, null, 2) }]
          };
          break;
        }
        
        case 'get_jira_fields': {
          const fieldsResult = await getFields.getJiraFields();
          result = {
            content: [{ type: 'text', text: JSON.stringify(fieldsResult, null, 2) }]
          };
          break;
        }
        
        case 'add_jira_comment': {
          const args = addComment.AddJiraCommentSchema.parse(request.params.arguments);
          const commentResult = await addComment.addJiraComment(args);
          result = {
            content: [{ type: 'text', text: JSON.stringify(commentResult, null, 2) }]
          };
          break;
        }
        
        case 'create_jira_issue': {
          const args = create.CreateJiraIssueSchema.parse(request.params.arguments);
          const createResult = await create.createJiraIssue(args);
          result = {
            content: [{ type: 'text', text: JSON.stringify(createResult, null, 2) }]
          };
          break;
        }
        
        case 'update_jira_issue': {
          const args = update.UpdateJiraIssueSchema.parse(request.params.arguments);
          const updateResult = await update.updateJiraIssue(args);
          result = {
            content: [{ type: 'text', text: JSON.stringify(updateResult, null, 2) }]
          };
          break;
        }
        
        case 'transition_jira_status': {
          const args = status.TransitionJiraStatusSchema.parse(request.params.arguments);
          const transitionResult = await status.transitionJiraStatus(args);
          result = {
            content: [{ type: 'text', text: JSON.stringify(transitionResult, null, 2) }]
          };
          break;
        }
        
        case 'transition_jira_status_by_name': {
          const { issueIdOrKey, statusName, comment, resolution, fields } = z.object({
            issueIdOrKey: z.string(),
            statusName: z.string(),
            comment: z.string().optional(),
            resolution: z.object({ name: z.string() }).optional(),
            fields: z.record(z.any()).optional()
          }).parse(request.params.arguments);
          
          const transitionResult = await status.transitionJiraStatusByName(
            issueIdOrKey,
            statusName,
            comment,
            resolution,
            fields
          );
          result = {
            content: [{ type: 'text', text: JSON.stringify(transitionResult, null, 2) }]
          };
          break;
        }
        
        case 'get_jira_transitions': {
          const { issueIdOrKey } = z.object({ issueIdOrKey: z.string() }).parse(request.params.arguments);
          const transitionsResult = await status.getJiraTransitions(issueIdOrKey);
          result = {
            content: [{ type: 'text', text: JSON.stringify(transitionsResult, null, 2) }]
          };
          break;
        }
        
        default:
          return res.status(400).json({
            jsonrpc: '2.0',
            id: request.id,
            error: { code: -32601, message: `Unknown tool: ${request.params.name}` }
          });
      }

      return res.json({
        jsonrpc: '2.0',
        id: request.id,
        result: result
      });

    } catch (error) {
      process.stderr.write(`Direct tool call error: ${error}\n`);
      return res.status(500).json({
        jsonrpc: '2.0',
        id: req.body.id,
        error: { code: -32603, message: `Tool execution failed: ${error}` }
      });
    }
  }

  // MCP message endpoint without session ID (for direct communication)
  app.post('/message/:sessionId', async (req, res) => {
    try {
      const { sessionId } = req.params;
      const transport = activeTransports.get(sessionId);
      
      if (!transport) {
        return res.status(404).json({ error: 'Session not found' });
      }

      await transport.handlePostMessage(req, res, req.body);
      
    } catch (error) {
      process.stderr.write(`Error handling message for session ${req.params.sessionId}: ${error}\n`);
      res.status(500).json({ error: 'Failed to process message' });
    }
  });

  httpServer.listen(port, () => {
    process.stderr.write(`Corporate Jira MCP Server running on HTTP port ${port}\n`);
    process.stderr.write(`SSE endpoint: http://localhost:${port}/sse\n`);
    process.stderr.write(`Message endpoint: http://localhost:${port}/message\n`);
  });
}

runServer().catch((error) => {
  console.error("Fatal error in main():", error);
  process.exit(1);
});