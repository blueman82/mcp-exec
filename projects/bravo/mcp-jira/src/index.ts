import express, { type Request, type Response } from "express";
import { z } from "zod";
import { loadEnvironment } from "./env.js";
import { loadConfig, config } from "./config.js";

import { testAuthSchema, testAuthHandler } from "./operations/auth.js";
import { searchSchema, searchHandler } from "./operations/search.js";
import { addCommentSchema, addCommentHandler } from "./operations/addComment.js";
import { deleteCommentSchema, deleteCommentHandler } from "./operations/deleteComment.js";
import {
  getTransitionsSchema,
  getTransitionsHandler,
  transitionSchema,
  transitionHandler,
} from "./operations/status.js";
import { createIssueSchema, createIssueHandler } from "./operations/create.js";
import { updateIssueSchema, updateIssueHandler } from "./operations/update.js";
import { getProjectIssueTypesSchema, getProjectIssueTypesHandler } from "./operations/createmeta.js";
import { downloadAttachmentSchema, downloadAttachmentHandler } from "./operations/attachment.js";

interface ToolEntry {
  schema: z.ZodType;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- handlers accept Zod-validated data, cast is safe
  handler: (args: any) => Promise<unknown>;
}

const tools: Record<string, ToolEntry> = {
  test_jira_auth: { schema: testAuthSchema, handler: testAuthHandler },
  search_jira_issues: { schema: searchSchema, handler: searchHandler },
  add_jira_comment: { schema: addCommentSchema, handler: addCommentHandler },
  delete_jira_comment: { schema: deleteCommentSchema, handler: deleteCommentHandler },
  get_jira_transitions: { schema: getTransitionsSchema, handler: getTransitionsHandler },
  transition_jira_status: { schema: transitionSchema, handler: transitionHandler },
  create_jira_issue: { schema: createIssueSchema, handler: createIssueHandler },
  update_jira_issue: { schema: updateIssueSchema, handler: updateIssueHandler },
  get_project_issue_types: { schema: getProjectIssueTypesSchema, handler: getProjectIssueTypesHandler },
  download_attachment: { schema: downloadAttachmentSchema, handler: downloadAttachmentHandler },
};

interface JsonRpcRequest {
  jsonrpc: string;
  id: string | number;
  method: string;
  params?: {
    name?: string;
    arguments?: unknown;
  };
}

function jsonRpcError(id: string | number | null, code: number, message: string): object {
  return { jsonrpc: "2.0", id, error: { code, message } };
}

function jsonRpcSuccess(id: string | number, result: unknown): object {
  return {
    jsonrpc: "2.0",
    id,
    result: {
      content: [{ type: "text", text: JSON.stringify(result) }],
    },
  };
}

async function main(): Promise<void> {
  await loadEnvironment();
  loadConfig();

  const app = express();
  app.use(express.json({ limit: "10mb" }));

  app.get("/health", (_req: Request, res: Response): void => {
    res.json({ status: "ok", tools: Object.keys(tools) });
  });

  app.post("/message", async (req: Request, res: Response): Promise<void> => {
    const body = req.body as JsonRpcRequest;
    const id = body.id ?? null;

    if (body.method !== "tools/call") {
      res.json(jsonRpcError(id, -32601, "Method not found"));
      return;
    }

    const toolName = body.params?.name;
    if (!toolName || !(toolName in tools)) {
      res.json(jsonRpcError(id, -32602, `Unknown tool: ${toolName ?? "undefined"}`));
      return;
    }

    const tool = tools[toolName];
    const parseResult = tool.schema.safeParse(body.params?.arguments ?? {});

    if (!parseResult.success) {
      const issues = parseResult.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; ");
      res.json(jsonRpcError(id, -32602, `Invalid arguments: ${issues}`));
      return;
    }

    try {
      const result = await tool.handler(parseResult.data);
      res.json(jsonRpcSuccess(id as string | number, result));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unknown error";
      res.json(jsonRpcError(id, -32000, message));
    }
  });

  const port = config.port;
  app.listen(port, () => {
    console.log(`Jira MCP server listening on port ${port}`);
    console.log(`Mode: ${config.mode}`);
    console.log(`Tools: ${Object.keys(tools).join(", ")}`);
  });
}

main().catch((err: unknown) => {
  console.error("Failed to start server:", err);
  process.exit(1);
});
