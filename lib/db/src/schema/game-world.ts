import {
  bigint,
  integer,
  jsonb,
  pgTable,
  primaryKey,
  text,
  timestamp,
} from "drizzle-orm/pg-core";

export type GameResourceSnapshot = {
  food: number;
  wood: number;
  stone: number;
  iron: number;
};

export type GameBuildingSnapshot = {
  id: string;
  name: string;
  level: number;
  description: string;
};

export type GameResearchSnapshot = {
  id: string;
  name: string;
  level: number;
  description: string;
};

export type GameArmySnapshot = {
  scout: number;
  infantry: number;
  cavalry: number;
  archer: number;
};

export const gameKingdomsTable = pgTable("game_kingdoms", {
  telegramUserId: bigint("telegram_user_id", { mode: "number" }).primaryKey(),
  name: text("name").notNull(),
  mapX: integer("map_x").notNull().default(3),
  mapY: integer("map_y").notNull().default(2),
  cityLevel: integer("city_level").notNull().default(1),
  power: integer("power").notNull().default(120),
  resources: jsonb("resources").$type<GameResourceSnapshot>().notNull(),
  buildings: jsonb("buildings").$type<GameBuildingSnapshot[]>().notNull(),
  research: jsonb("research").$type<GameResearchSnapshot[]>().notNull(),
  army: jsonb("army").$type<GameArmySnapshot>().notNull(),
  discoveredTiles: jsonb("discovered_tiles").$type<string[]>().notNull(),
  lastCollectedAt: timestamp("last_collected_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export const gameAlliancesTable = pgTable("game_alliances", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  tag: text("tag").notNull().unique(),
  leaderId: bigint("leader_id", { mode: "number" }).notNull(),
  memberCount: integer("member_count").notNull().default(1),
  description: text("description").notNull().default("Новый союз для тех, кто строит историю."),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const gameAllianceMembersTable = pgTable(
  "game_alliance_members",
  {
    allianceId: text("alliance_id").notNull(),
    telegramUserId: bigint("telegram_user_id", { mode: "number" }).notNull(),
    role: text("role").notNull().default("member"),
    joinedAt: timestamp("joined_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => ({
    primaryKey: primaryKey({ columns: [table.allianceId, table.telegramUserId] }),
  }),
);

export const gameWorldEventsTable = pgTable("game_world_events", {
  id: text("id").primaryKey(),
  title: text("title").notNull(),
  description: text("description").notNull(),
  progress: integer("progress").notNull().default(0),
  goal: integer("goal").notNull(),
  startsAt: timestamp("starts_at", { withTimezone: true }).notNull(),
  endsAt: timestamp("ends_at", { withTimezone: true }).notNull(),
  reward: text("reward").notNull(),
});

export const gameBattleReportsTable = pgTable("game_battle_reports", {
  id: text("id").primaryKey(),
  attackerId: bigint("attacker_id", { mode: "number" }).notNull(),
  battleType: text("battle_type").notNull(),
  opponent: text("opponent").notNull(),
  result: text("result").notNull(),
  powerDelta: integer("power_delta").notNull().default(0),
  reward: text("reward").notNull().default("—"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export type GameKingdom = typeof gameKingdomsTable.$inferSelect;
export type GameAlliance = typeof gameAlliancesTable.$inferSelect;
export type GameAllianceMember = typeof gameAllianceMembersTable.$inferSelect;
export type GameWorldEvent = typeof gameWorldEventsTable.$inferSelect;
export type GameBattleReport = typeof gameBattleReportsTable.$inferSelect;