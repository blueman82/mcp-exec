import { z } from "zod";
import { jiraRequest } from "../utils.js";

export const testAuthSchema = z.object({});

export async function testAuthHandler(
  _args: z.infer<typeof testAuthSchema>
): Promise<unknown> {
  return jiraRequest("/myself");
}
