import { requiredEnv } from "../config/env";
import { isSameSecret } from "../security/sha256";
import { bearerToken } from "./bearerToken";

export async function isServiceCaller(request: Request): Promise<boolean> {
  const presentedKey = bearerToken(request);
  if (presentedKey === null) {
    return false;
  }
  return isSameSecret(presentedKey, requiredEnv("SERVICE_API_KEY"));
}
