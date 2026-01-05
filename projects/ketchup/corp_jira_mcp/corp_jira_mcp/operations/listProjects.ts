import { z } from "zod";
import { jiraRequest, buildUrl } from "../common/utils.js";

// Schema for list projects request
export const ListProjectsSchema = z.object({
  expand: z.string().optional(),
  recent: z.number().optional(),
  properties: z.array(z.string()).optional()
});

export type ListProjectsRequest = z.infer<typeof ListProjectsSchema>;

/**
 * Lists all JIRA projects visible to the authenticated user
 * @param params Optional parameters for filtering and expanding project data
 * @returns List of projects with success wrapper
 */
export async function listJiraProjects(params: ListProjectsRequest = {}) {
  try {
    // Build query parameters
    const queryParams: Record<string, string | undefined> = {};

    if (params.expand) {
      queryParams.expand = params.expand;
    }

    if (params.recent !== undefined) {
      queryParams.recent = params.recent.toString();
    }

    if (params.properties && params.properties.length > 0) {
      queryParams.properties = params.properties.join(',');
    }

    // Build URL with query parameters
    const url = buildUrl("project", queryParams);

    const response = await jiraRequest(url, {
      method: "GET"
    });

    // Response is an array of projects
    const projects = Array.isArray(response) ? response : [];

    return {
      success: true,
      message: `Found ${projects.length} projects`,
      data: projects
    };
  } catch (error) {
    return {
      success: false,
      message: error instanceof Error ? error.message : 'Unknown error occurred',
      error
    };
  }
}
