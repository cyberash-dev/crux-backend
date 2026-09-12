export async function sha256Hex(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

/* Comparing digests instead of the raw strings keeps the comparison time
   independent of how many leading characters of the secret were guessed. */
export async function isSameSecret(presented: string, expected: string): Promise<boolean> {
  const [presentedDigest, expectedDigest] = await Promise.all([
    sha256Hex(presented),
    sha256Hex(expected),
  ]);
  return presentedDigest === expectedDigest;
}
