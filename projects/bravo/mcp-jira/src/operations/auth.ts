import { z } from "zod";
import { jiraRequest } from "../utils.js";

export const testAuthSchema = z.object({
  userPat: z.string().optional(),
});

export async function testAuthHandler(
  args: z.infer<typeof testAuthSchema>
): Promise<unknown> {
  const { userPat } = args;
  return jiraRequest("/myself", { userPat });
}
