const RUN_TOKEN_BYTES = 32;

export function newRunToken(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(RUN_TOKEN_BYTES));
  const binary = Array.from(bytes, (byte) => String.fromCharCode(byte)).join("");
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
