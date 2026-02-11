import { z } from "zod";
import { jiraRequest } from "../utils.js";

export const addCommentSchema = z.object({
  issueIdOrKey: z.string(),
  comment: z.object({ body: z.string() }),
  userPat: z.string().optional(),
});

export async function addCommentHandler(
  args: z.infer<typeof addCommentSchema>
): Promise<unknown> {
  const { issueIdOrKey, comment, userPat } = args;

  return jiraRequest(`/issue/${issueIdOrKey}/comment`, {
    method: "POST",
    body: { body: comment.body },
    userPat,
  });
}
