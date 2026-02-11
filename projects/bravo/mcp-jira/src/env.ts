import dotenv from "dotenv";
import { loadAwsSecrets } from "./env-aws.js";

export async function loadEnvironment(): Promise<void> {
  if (process.env.USE_AWS_SECRETS === "true") {
    await loadAwsSecrets();
  }

  dotenv.config();
}
