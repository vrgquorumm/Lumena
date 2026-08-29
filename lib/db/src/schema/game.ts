import { relations } from "drizzle-orm";
import {
  bigint,
  integer,
  pgTable,
  primaryKey,
  text,
  timestamp,
} from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const gamePlayersTable = pgTable("game_players", {
  telegramUserId: bigint("telegram_user_id", { mode: "number" }).primaryKey(),
  displayName: text("display_name").notNull(),
  level: integer("level").notNull().default(1),
  xp: integer("xp").notNull().default(0),
  gameLmn: integer("game_lmn").notNull().default(0),
  streak: integer("streak").notNull().default(0),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true })
    .notNull()
    .defaultNow()
    .$onUpdate(() => new Date()),
});

export const gameQuestsTable = pgTable("game_quests", {
  id: text("id").primaryKey(),
  title: text("title").notNull(),
  description: text("description").notNull(),
  locationId: text("location_id").notNull(),
  rewardLmn: integer("reward_lmn").notNull(),
  goal: integer("goal").notNull().default(1),
  sortOrder: integer("sort_order").notNull().default(0),
});

export const gameQuestProgressTable = pgTable(
  "game_quest_progress",
  {
    telegramUserId: bigint("telegram_user_id", { mode: "number" }).notNull(),
    questId: text("quest_id").notNull(),
    status: text("status").notNull().default("available"),
    progress: integer("progress").notNull().default(0),
    startedAt: timestamp("started_at", { withTimezone: true }),
    claimedAt: timestamp("claimed_at", { withTimezone: true }),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .notNull()
      .defaultNow()
      .$onUpdate(() => new Date()),
  },
  (table) => ({
    primaryKey: primaryKey({ columns: [table.telegramUserId, table.questId] }),
  }),
);

export const gameRewardClaimsTable = pgTable(
  "game_reward_claims",
  {
    telegramUserId: bigint("telegram_user_id", { mode: "number" }).notNull(),
    questId: text("quest_id").notNull(),
    rewardLmn: integer("reward_lmn").notNull(),
    claimedAt: timestamp("claimed_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => ({
    primaryKey: primaryKey({ columns: [table.telegramUserId, table.questId] }),
  }),
);

export const gamePlayersRelations = relations(gamePlayersTable, ({ many }) => ({
  questProgress: many(gameQuestProgressTable),
  rewardClaims: many(gameRewardClaimsTable),
}));

export const gameQuestProgressRelations = relations(
  gameQuestProgressTable,
  ({ one }) => ({
    player: one(gamePlayersTable, {
      fields: [gameQuestProgressTable.telegramUserId],
      references: [gamePlayersTable.telegramUserId],
    }),
    quest: one(gameQuestsTable, {
      fields: [gameQuestProgressTable.questId],
      references: [gameQuestsTable.id],
    }),
  }),
);

export const gameRewardClaimsRelations = relations(
  gameRewardClaimsTable,
  ({ one }) => ({
    player: one(gamePlayersTable, {
      fields: [gameRewardClaimsTable.telegramUserId],
      references: [gamePlayersTable.telegramUserId],
    }),
  }),
);

export const insertGamePlayerSchema = createInsertSchema(gamePlayersTable).omit({
  createdAt: true,
  updatedAt: true,
});
export type InsertGamePlayer = z.infer<typeof insertGamePlayerSchema>;
export type GamePlayer = typeof gamePlayersTable.$inferSelect;
export type GameQuest = typeof gameQuestsTable.$inferSelect;
export type GameQuestProgress = typeof gameQuestProgressTable.$inferSelect;
export type GameRewardClaim = typeof gameRewardClaimsTable.$inferSelect;