import { drizzle } from "drizzle-orm/node-postgres";
import pg from "pg";
import * as schema from "./schema";

const { Pool } = pg;

if (!process.env.DATABASE_URL) {
  throw new Error(
    "DATABASE_URL must be set. Did you forget to provision a database?",
  );
}

const databaseUrl = process.env.DATABASE_URL;
const parsedDatabaseUrl = new URL(databaseUrl);
const sslMode = parsedDatabaseUrl.searchParams.get("sslmode");

// Railway's public TCP proxy uses a certificate issued for the proxy
// infrastructure rather than the database hostname. Keep TLS encryption
// enabled for that connection while skipping hostname verification.
const ssl =
  sslMode === "disable"
    ? false
    : sslMode === "require" || !parsedDatabaseUrl.hostname.endsWith(".internal")
      ? { rejectUnauthorized: false }
      : undefined;

export const pool = new Pool({
  connectionString: databaseUrl,
  ...(ssl === undefined ? {} : { ssl }),
});
export const db = drizzle(pool, { schema });

export * from "./schema";
