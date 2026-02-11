import { z } from "zod";
import { writeFile } from "node:fs/promises";
import { getConfig } from "../config.js";
import { getIpaasAuth } from "../ketchup-secrets.js";

export const downloadAttachmentSchema = z.object({
  issueIdOrKey: z.string(),
  attachmentId: z.string(),
  destinationPath: z.string(),
});

export async function downloadAttachmentHandler(
  args: z.infer<typeof downloadAttachmentSchema>
): Promise<unknown> {
  const { attachmentId, destinationPath } = args;
  const cfg = getConfig();

  const url = `${cfg.baseUrl}/attachment/content/${attachmentId}`;
  const headers: Record<string, string> = {
    Accept: "application/octet-stream",
  };

  if (cfg.mode === "ipaas") {
    const ipaasAuth = await getIpaasAuth();
    if (!ipaasAuth) {
      throw new Error("iPaaS auth not available for attachment download");
    }
    headers["Authorization"] = ipaasAuth.imsToken;
    headers["Api_key"] = ipaasAuth.apiKey;
    headers["x-authorization"] = `Bearer ${cfg.auth.pat}`;
  } else {
    headers["Authorization"] = `Bearer ${cfg.auth.pat}`;
  }

  const response = await fetch(url, { headers });

  if (!response.ok) {
    throw new Error(
      `Failed to download attachment: ${response.status} ${response.statusText}`
    );
  }

  const buffer = Buffer.from(await response.arrayBuffer());
  await writeFile(destinationPath, buffer);

  return { success: true, path: destinationPath, size: buffer.byteLength };
}
