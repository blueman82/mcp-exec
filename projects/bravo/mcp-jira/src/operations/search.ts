import { z } from "zod";
import { jiraRequest } from "../utils.js";

export const searchSchema = z.object({
  jql: z.string(),
  startAt: z.number().optional().default(0),
  maxResults: z.number().optional().default(50),
  fields: z.array(z.string()).optional(),
  minimizeOutput: z.boolean().optional().default(false),
});

const KEEP_FIELDS = new Set([
  "key",
  "id",
  "self",
  "summary",
  "status",
  "assignee",
  "updated",
  "comment",
]);

function minimizeIssue(issue: Record<string, unknown>): Record<string, unknown> {
  const fields = issue["fields"] as Record<string, unknown> | undefined;
  if (!fields) return issue;

  const minimized: Record<string, unknown> = {};
  for (const key of Object.keys(fields)) {
    if (KEEP_FIELDS.has(key)) {
      minimized[key] = fields[key];
    }
  }

  return { ...issue, fields: minimized };
}

export async function searchHandler(
  args: z.infer<typeof searchSchema>
): Promise<unknown> {
  const { jql, startAt, maxResults, fields, minimizeOutput } = args;

  const result = await jiraRequest<Record<string, unknown>>("/search", {
    method: "POST",
    body: { jql, startAt, maxResults, fields },
  });

  if (minimizeOutput && Array.isArray(result["issues"])) {
    result["issues"] = (result["issues"] as Record<string, unknown>[]).map(
      minimizeIssue
    );
  }

  return { data: result };
}
