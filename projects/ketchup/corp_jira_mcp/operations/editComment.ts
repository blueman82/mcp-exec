import { z } from "zod";
import { jiraRequest } from "../common/utils.js";
import { formatResponse, handleOperationError } from "./update.js";

// Schema for comment body
const CommentBodySchema = z.object({
  body: z.string(),
  visibility: z.object({
    type: z.string(),
    value: z.string()
  }).optional()
});

// Schema for edit comment request
export const EditJiraCommentSchema = z.object({
  issueIdOrKey: z.string(),
  commentId: z.string(),
  comment: CommentBodySchema
});

export type EditJiraCommentRequest = z.infer<typeof EditJiraCommentSchema>;

/**
 * Edits an existing comment on a Jira issue
 * @param params The parameters for editing a comment
 * @returns The result of the operation
 */
export async function editJiraComment(params: EditJiraCommentRequest) {
  const { issueIdOrKey, commentId, comment } = params;

  try {
    const response = await jiraRequest(`issue/${issueIdOrKey}/comment/${commentId}`, {
      method: "PUT",
      body: comment
    });

    return formatResponse(true, "Comment edited successfully", response);
  } catch (error) {
    return handleOperationError(error, "editing comment");
  }
}
