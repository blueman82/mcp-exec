import { z } from "zod";
import { jiraRequest } from "../utils.js";

export const updateIssueSchema = z.object({
  issueIdOrKey: z.string(),
  fields: z.record(z.unknown()),
  userPat: z.string().optional(),
});

export async function updateIssueHandler(
  args: z.infer<typeof updateIssueSchema>
): Promise<unknown> {
  const { issueIdOrKey, fields, userPat } = args;

  return jiraRequest(`/issue/${issueIdOrKey}`, {
    method: "PUT",
    body: { fields },
    userPat,
  });
}
