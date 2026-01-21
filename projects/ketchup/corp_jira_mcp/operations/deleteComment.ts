import { z } from "zod";
import { jiraRequest } from "../common/utils.js";
import { formatResponse, handleOperationError } from "./update.js";

// Schema for delete comment request
export const DeleteJiraCommentSchema = z.object({
  issueIdOrKey: z.string(),
  commentId: z.string()
});

export type DeleteJiraCommentRequest = z.infer<typeof DeleteJiraCommentSchema>;

/**
 * Deletes a comment from a Jira issue
 * @param params The parameters for deleting a comment
 * @returns The result of the operation
 */
export async function deleteJiraComment(params: DeleteJiraCommentRequest) {
  const { issueIdOrKey, commentId } = params;

  try {
    await jiraRequest(`issue/${issueIdOrKey}/comment/${commentId}`, {
      method: "DELETE"
    });

    return formatResponse(true, `Comment ${commentId} deleted from ${issueIdOrKey}`);
  } catch (error) {
    return handleOperationError(error, "deleting comment");
  }
}
