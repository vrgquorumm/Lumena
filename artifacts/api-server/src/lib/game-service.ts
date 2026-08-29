import { and, asc, eq, sql } from "drizzle-orm";
import { db } from "@workspace/db";
import {
  gamePlayersTable,
  gameQuestProgressTable,
  gameQuestsTable,
  gameRewardClaimsTable,
} from "@workspace/db";
import type { TelegramGameUser } from "./game-auth";
import { getStrategyState } from "./strategy-service";

export type GameRuleErrorCode = 400;

export class GameRuleError extends Error {
  readonly statusCode: GameRuleErrorCode = 400;

  constructor(message: string) {
    super(message);
    this.name = "GameRuleError";
  }
}

const LOCATIONS = [
  {
    id: "sunny-harbor",
    title: "Солнечная гавань",
    description: "Тёплый причал, где Лумка находит первые следы приключений.",
    accent: "#f7b955",
  },
  {
    id: "meow-market",
    title: "Мяу-маркет",
    description: "Рынок редких деталей, рецептов и полезных находок.",
    accent: "#f47f5f",
  },
  {
    id: "clock-square",
    title: "Часовая площадь",
    description: "Сердце города, где открываются новые маршруты.",
    accent: "#7ad4c4",
  },
];

const QUEST_SEED = [
  {
    id: "first-pawprints",
    title: "Первые следы",
    description: "Осмотрись в Солнечной гавани и найди место для будущего дома.",
    locationId: "sunny-harbor",
    rewardLmn: 120,
    goal: 1,
    sortOrder: 1,
  },
  {
    id: "market-supply",
    title: "Запасы для мастерской",
    description: "Загляни в Мяу-маркет и забери первую посылку для Лумки.",
    locationId: "meow-market",
    rewardLmn: 180,
    goal: 1,
    sortOrder: 2,
  },
  {
    id: "town-blueprint",
    title: "План большого города",
    description: "Доберись до Часовой площади и открой чертёж будущего мира.",
    locationId: "clock-square",
    rewardLmn: 260,
    goal: 1,
    sortOrder: 3,
  },
] as const;

type QuestStatus = "locked" | "available" | "in_progress" | "completed" | "claimed";

async function ensureQuestCatalog(): Promise<void> {
  await db.insert(gameQuestsTable).values([...QUEST_SEED]).onConflictDoNothing();
}

async function ensurePlayer(user: TelegramGameUser): Promise<void> {
  await db
    .insert(gamePlayersTable)
    .values({ telegramUserId: user.id, displayName: user.displayName })
    .onConflictDoNothing();
  await db
    .update(gamePlayersTable)
    .set({ displayName: user.displayName, updatedAt: new Date() })
    .where(eq(gamePlayersTable.telegramUserId, user.id));
}

function questStatus(
  index: number,
  row: typeof gameQuestProgressTable.$inferSelect | undefined,
  previousClaimed: boolean,
): QuestStatus {
  if (row) return row.status as QuestStatus;
  return index === 0 || previousClaimed ? "available" : "locked";
}

export async function loadGameState(user: TelegramGameUser) {
  await ensureQuestCatalog();
  await ensurePlayer(user);

  const [player] = await db
    .select()
    .from(gamePlayersTable)
    .where(eq(gamePlayersTable.telegramUserId, user.id));
  const quests = await db
    .select()
    .from(gameQuestsTable)
    .orderBy(asc(gameQuestsTable.sortOrder));
  const progressRows = await db
    .select()
    .from(gameQuestProgressTable)
    .where(eq(gameQuestProgressTable.telegramUserId, user.id));
  const progressByQuest = new Map(progressRows.map((row) => [row.questId, row]));

  let previousClaimed = true;
  const visibleQuests = quests.map((quest, index) => {
    const row = progressByQuest.get(quest.id);
    const status = questStatus(index, row, previousClaimed);
    if (status !== "claimed") previousClaimed = false;
    return {
      id: quest.id,
      title: quest.title,
      description: quest.description,
      locationId: quest.locationId,
      rewardLmn: quest.rewardLmn,
      progress: row?.progress ?? 0,
      goal: quest.goal,
      status,
    };
  });

  const claimedLocationIds = new Set(
    visibleQuests.filter((quest) => quest.status === "claimed").map((quest) => quest.locationId),
  );
  const locations = LOCATIONS.map((location, index) => ({
    ...location,
    state: (
      claimedLocationIds.has(location.id)
        ? "discovered"
        : index === 0 || visibleQuests[index - 1]?.status === "claimed"
          ? "available"
          : "locked"
    ) as "available" | "locked" | "discovered",
  }));
  const featuredQuest =
    visibleQuests.find((quest) => ["available", "in_progress", "completed"].includes(quest.status)) ??
    null;

  const legacyState = {
    player: {
      displayName: player?.displayName ?? user.displayName,
      level: player?.level ?? 1,
      xp: player?.xp ?? 0,
      xpToNext: Math.max(100, ((player?.level ?? 1) + 1) * 100),
      gameLmn: player?.gameLmn ?? 0,
    },
    locations,
    quests: visibleQuests,
    featuredQuestId: featuredQuest?.id ?? null,
    streak: player?.streak ?? 0,
  };
  return { ...legacyState, ...(await getStrategyState(user)) };
}

async function getQuest(questId: string) {
  const [quest] = await db
    .select()
    .from(gameQuestsTable)
    .where(eq(gameQuestsTable.id, questId));
  if (!quest) throw new GameRuleError("Задание не найдено.");
  return quest;
}

export async function startQuest(user: TelegramGameUser, questId: string) {
  await ensureQuestCatalog();
  await ensurePlayer(user);
  const quest = await getQuest(questId);
  const state = await loadGameState(user);
  const visibleQuest = state.quests.find((item) => item.id === questId);
  if (!visibleQuest) throw new GameRuleError("Задание не найдено.");
  if (visibleQuest.status === "locked") {
    throw new GameRuleError("Сначала выполни предыдущее задание.");
  }
  if (visibleQuest.status !== "available") return state;

  await db
    .insert(gameQuestProgressTable)
    .values({
      telegramUserId: user.id,
      questId: quest.id,
      status: "completed",
      progress: quest.goal,
      startedAt: new Date(),
      updatedAt: new Date(),
    })
    .onConflictDoNothing();
  return loadGameState(user);
}

export async function claimQuest(user: TelegramGameUser, questId: string) {
  await ensureQuestCatalog();
  await ensurePlayer(user);
  const quest = await getQuest(questId);
  const [progress] = await db
    .select()
    .from(gameQuestProgressTable)
    .where(
      and(
        eq(gameQuestProgressTable.telegramUserId, user.id),
        eq(gameQuestProgressTable.questId, quest.id),
      ),
    );
  if (!progress || progress.status === "locked" || progress.status === "available") {
    throw new GameRuleError("Сначала начни это задание.");
  }
  if (progress.status === "in_progress") {
    throw new GameRuleError("Задание ещё не завершено.");
  }
  if (progress.status === "claimed") return loadGameState(user);

  await db.transaction(async (tx) => {
    const [claim] = await tx
      .insert(gameRewardClaimsTable)
      .values({
        telegramUserId: user.id,
        questId: quest.id,
        rewardLmn: quest.rewardLmn,
      })
      .onConflictDoNothing()
      .returning();
    if (!claim) return;

    await tx
      .update(gameQuestProgressTable)
      .set({ status: "claimed", claimedAt: new Date(), updatedAt: new Date() })
      .where(
        and(
          eq(gameQuestProgressTable.telegramUserId, user.id),
          eq(gameQuestProgressTable.questId, quest.id),
        ),
      );
    await tx
      .update(gamePlayersTable)
      .set({
        gameLmn: sql`${gamePlayersTable.gameLmn} + ${quest.rewardLmn}`,
        xp: sql`${gamePlayersTable.xp} + ${quest.rewardLmn}`,
        updatedAt: new Date(),
      })
      .where(eq(gamePlayersTable.telegramUserId, user.id));
  });

  return loadGameState(user);
}