import { z } from "zod";
import { jiraRequest } from "../utils.js";

export const getProjectIssueTypesSchema = z.object({
  projectKey: z.string(),
});

export async function getProjectIssueTypesHandler(
  args: z.infer<typeof getProjectIssueTypesSchema>
): Promise<unknown> {
  return jiraRequest(`/project/${args.projectKey}/statuses`);
}
