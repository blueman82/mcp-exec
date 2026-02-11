import { z } from "zod";
import { jiraRequest } from "../utils.js";

export const getTransitionsSchema = z.object({
  issueIdOrKey: z.string(),
});

export async function getTransitionsHandler(
  args: z.infer<typeof getTransitionsSchema>
): Promise<unknown> {
  const result = await jiraRequest(`/issue/${args.issueIdOrKey}/transitions`);
  return { data: result };
}

export const transitionSchema = z.object({
  issueIdOrKey: z.string(),
  transitionId: z.string(),
  resolution: z.object({ name: z.string() }).optional(),
  userPat: z.string().optional(),
});

export async function transitionHandler(
  args: z.infer<typeof transitionSchema>
): Promise<unknown> {
  const { issueIdOrKey, transitionId, resolution, userPat } = args;

  const body: Record<string, unknown> = {
    transition: { id: transitionId },
  };

  if (resolution) {
    body["fields"] = { resolution };
  }

  return jiraRequest(`/issue/${issueIdOrKey}/transitions`, {
    method: "POST",
    body,
    userPat,
  });
}
