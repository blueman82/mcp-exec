import { z } from "zod";
import { jiraRequest } from "../utils.js";

export const createIssueSchema = z.object({
  fields: z.record(z.unknown()),
  userPat: z.string().optional(),
});

export async function createIssueHandler(
  args: z.infer<typeof createIssueSchema>
): Promise<unknown> {
  const { fields, userPat } = args;

  return jiraRequest("/issue", {
    method: "POST",
    body: { fields },
    userPat,
  });
}
