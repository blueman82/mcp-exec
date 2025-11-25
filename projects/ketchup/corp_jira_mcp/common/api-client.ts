/**
 * API Client wrapper for testability
 * This provides a mockable interface to jiraRequest
 */
import { jiraRequest } from './utils.js';

export const apiClient = {
  jiraRequest
};
