import { createHmac, timingSafeEqual } from "node:crypto";

export type TelegramGameUser = {
  id: number;
  displayName: string;
};

export class GameAuthError extends Error {
  constructor(
    message: string,
    public readonly statusCode = 401,
  ) {
    super(message);
    this.name = "GameAuthError";
  }
}

function getBotToken(): string {
  const token = process.env.BOT_TOKEN?.trim();
  if (!token) {
    throw new GameAuthError("Telegram game authentication is not configured.", 503);
  }
  return token;
}

export function validateTelegramInitData(initData: string): TelegramGameUser {
  if (!initData?.trim()) {
    throw new GameAuthError("Telegram session is required.");
  }

  const params = new URLSearchParams(initData);
  const receivedHash = params.get("hash");
  const authDate = Number(params.get("auth_date"));
  const userRaw = params.get("user");
  if (!receivedHash || !userRaw || !Number.isFinite(authDate)) {
    throw new GameAuthError("Telegram session is incomplete.");
  }

  const ageSeconds = Math.floor(Date.now() / 1000) - authDate;
  if (ageSeconds > 24 * 60 * 60 || ageSeconds < -5 * 60) {
    throw new GameAuthError("Telegram session has expired.");
  }

  const dataCheckString = [...params.entries()]
    .filter(([key]) => key !== "hash")
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, value]) => `${key}=${value}`)
    .join("\n");

  const secretKey = createHmac("sha256", "WebAppData")
    .update(getBotToken())
    .digest();
  const calculatedHash = createHmac("sha256", secretKey)
    .update(dataCheckString)
    .digest("hex");
  const expected = Buffer.from(calculatedHash, "hex");
  const received = Buffer.from(receivedHash, "hex");
  if (expected.length !== received.length || !timingSafeEqual(expected, received)) {
    throw new GameAuthError("Telegram session signature is invalid.");
  }

  try {
    const user = JSON.parse(userRaw) as {
      id?: unknown;
      first_name?: unknown;
      last_name?: unknown;
      username?: unknown;
    };
    if (typeof user.id !== "number" || !Number.isSafeInteger(user.id) || user.id <= 0) {
      throw new Error("invalid id");
    }
    const firstName = typeof user.first_name === "string" ? user.first_name.trim() : "";
    const lastName = typeof user.last_name === "string" ? user.last_name.trim() : "";
    const username = typeof user.username === "string" ? user.username.trim() : "";
    const displayName = [firstName, lastName].filter(Boolean).join(" ") || username || "Игрок";
    return { id: user.id, displayName: displayName.slice(0, 80) };
  } catch {
    throw new GameAuthError("Telegram user data is invalid.");
  }
}