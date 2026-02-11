import { z } from "zod";
import { jiraRequest } from "../utils.js";

export const deleteCommentSchema = z.object({
  issueIdOrKey: z.string(),
  commentId: z.string(),
  userPat: z.string().optional(),
});

export async function deleteCommentHandler(
  args: z.infer<typeof deleteCommentSchema>
): Promise<unknown> {
  const { issueIdOrKey, commentId, userPat } = args;

  return jiraRequest(`/issue/${issueIdOrKey}/comment/${commentId}`, {
    method: "DELETE",
    userPat,
  });
}
