import { configuredProxyUrls } from "../config/proxyUrls";

const SECRET_ENV_NAMES = [
  "DAYTONA_API_KEY",
  "PROXY_URL",
  "CLAUDE_CODE_OAUTH_TOKEN",
  "ELEVENLABS_API_KEY",
  "EXA_API_KEY",
  "SERVICE_API_KEY",
] as const;

const REDACTION_MARK = "[redacted]";

export function redactedText(text: string, extraSecrets: readonly string[] = []): string {
  const configuredSecrets = SECRET_ENV_NAMES.map((name) => process.env[name] ?? "");
  return [...configuredSecrets, ...configuredProxyUrls(), ...extraSecrets]
    .filter((secret) => secret.length > 0)
    .reduce((redacted, secret) => redacted.split(secret).join(REDACTION_MARK), text);
}

export function redactedErrorMessage(error: unknown, extraSecrets: readonly string[] = []): string {
  const message = error instanceof Error ? error.message : String(error);
  return redactedText(message, extraSecrets);
}
