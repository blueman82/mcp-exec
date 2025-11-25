import { z } from 'zod';
import { jiraRequest } from '../common/utils.js';

export const GetFieldsSchema = z.object({
  // No parameters needed - returns all fields
});

export async function getJiraFields() {
  /**
   * Fetches all available JIRA fields including custom fields
   * Returns field metadata including ID, name, type, and whether it's custom
   */
  const fields = await jiraRequest('field');
  
  // Optionally filter/format the response
  return fields;
}

export type GetFieldsInput = z.infer<typeof GetFieldsSchema>;