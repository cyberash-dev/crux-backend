import type { DatabaseWriter } from "../_generated/server";
import { configuredProxyUrls } from "../config/proxyUrls";

/* Turns whose proxy already blocked the run are skipped but still counted,
   so the next sandbox creation continues after the turn taken here. */
export async function takeProxyIndex(
  db: DatabaseWriter,
  blockedProxyIndexes: readonly number[],
): Promise<number | null> {
  const proxyCount = configuredProxyUrls().length;
  if (proxyCount === 0) {
    return null;
  }
  const rotation = await db.query("proxy_rotation").first();
  const turn = untriedTurn(rotation?.turns_taken ?? 0, proxyCount, blockedProxyIndexes);
  if (rotation === null) {
    await db.insert("proxy_rotation", { turns_taken: turn + 1 });
  } else {
    await db.patch("proxy_rotation", rotation._id, { turns_taken: turn + 1 });
  }
  return turn % proxyCount;
}

export function hasUntriedProxy(blockedProxyIndexes: readonly number[], proxyCount: number): boolean {
  return Array.from({ length: proxyCount }, (_, index) => index).some(
    (index) => !blockedProxyIndexes.includes(index),
  );
}

function untriedTurn(firstTurn: number, proxyCount: number, blockedProxyIndexes: readonly number[]): number {
  const candidateTurns = Array.from({ length: proxyCount }, (_, offset) => firstTurn + offset);
  return candidateTurns.find((turn) => !blockedProxyIndexes.includes(turn % proxyCount)) ?? firstTurn;
}
