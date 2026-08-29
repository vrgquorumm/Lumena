import { randomUUID } from "node:crypto";
import { and, asc, desc, eq, sql } from "drizzle-orm";
import { db } from "@workspace/db";
import {
  gameAllianceMembersTable,
  gameAlliancesTable,
  gameBattleReportsTable,
  gameKingdomsTable,
  gameWorldEventsTable,
} from "@workspace/db";
import type { TelegramGameUser } from "./game-auth";
import type {
  GameArmySnapshot,
  GameBuildingSnapshot,
  GameKingdom,
  GameResourceSnapshot,
  GameResearchSnapshot,
} from "@workspace/db";

type StrategyAction =
  | "collect_resources"
  | "upgrade_building"
  | "research"
  | "train_army"
  | "scout"
  | "attack_npc"
  | "attack_player"
  | "create_alliance"
  | "join_alliance"
  | "leave_alliance"
  | "contribute_event";

export type StrategyCommand = {
  action: StrategyAction;
  targetId?: string;
  quantity?: number;
  name?: string;
  tag?: string;
};

export class StrategyRuleError extends Error {
  readonly statusCode = 400;

  constructor(message: string) {
    super(message);
    this.name = "StrategyRuleError";
  }
}

const RESOURCE_KEYS = ["food", "wood", "stone", "iron"] as const;
type ResourceKey = (typeof RESOURCE_KEYS)[number];

const BUILDING_SEED: GameBuildingSnapshot[] = [
  { id: "city-hall", name: "Цитадель", level: 1, description: "Сердце королевства. Повышает предел развития." },
  { id: "barracks", name: "Казармы", level: 1, description: "Готовят пехоту для защиты границ." },
  { id: "academy", name: "Академия", level: 1, description: "Открывает новые знания и тактики." },
  { id: "lumber-mill", name: "Лесопилка", level: 1, description: "Ускоряет производство древесины." },
  { id: "watchtower", name: "Дозорная башня", level: 1, description: "Расширяет обзор на мировой карте." },
];

const RESEARCH_SEED: GameResearchSnapshot[] = [
  { id: "agriculture", name: "Севооборот", level: 0, description: "Больше еды для растущего королевства." },
  { id: "masonry", name: "Каменная кладка", level: 0, description: "Прочнее стены и быстрее стройка." },
  { id: "military-doctrine", name: "Военная доктрина", level: 0, description: "Сила отрядов растёт с каждым уровнем." },
];

const ARMY_SEED: GameArmySnapshot = {
  scout: 3,
  infantry: 20,
  cavalry: 4,
  archer: 8,
};

const RESOURCE_SEED: GameResourceSnapshot = {
  food: 1200,
  wood: 950,
  stone: 700,
  iron: 350,
};

const WORLD_TILES = [
  { id: "capital", x: 3, y: 2, label: "Столица", terrain: "citadel", kind: "capital", power: 120, reward: null },
  { id: "sunfield", x: 1, y: 1, label: "Солнечные поля", terrain: "plains", kind: "resource", power: 0, reward: "+120 еды" },
  { id: "ironridge", x: 5, y: 1, label: "Железный кряж", terrain: "mountain", kind: "resource", power: 0, reward: "+80 железа" },
  { id: "old-ruins", x: 1, y: 3, label: "Старые руины", terrain: "ruins", kind: "ruins", power: 240, reward: "древний артефакт" },
  { id: "wolf-pass", x: 5, y: 3, label: "Волчий перевал", terrain: "forest", kind: "npc", power: 420, reward: "250 дерева" },
  { id: "watcher-lake", x: 3, y: 4, label: "Озеро Наблюдателя", terrain: "lake", kind: "event", power: 0, reward: "очки события" },
  { id: "border-road", x: 2, y: 4, label: "Пограничный тракт", terrain: "road", kind: "player", power: 560, reward: "PvP-разведка" },
  { id: "amber-grove", x: 4, y: 1, label: "Янтарная роща", terrain: "forest", kind: "resource", power: 0, reward: "+100 дерева" },
  { id: "north-gate", x: 4, y: 4, label: "Северные ворота", terrain: "road", kind: "npc", power: 680, reward: "редкий трофей" },
] as const;

const EVENT_SEED = {
  id: "winter-road",
  title: "Дорога сквозь зиму",
  description: "Соберите общий караван ресурсов, пока снежные перевалы не закрылись.",
  goal: 120,
  reward: "1 200 очков королевства",
};

function cloneResources(resources: GameResourceSnapshot): GameResourceSnapshot {
  return { food: resources.food, wood: resources.wood, stone: resources.stone, iron: resources.iron };
}

function resourceCost(level: number, kind: "building" | "research"): GameResourceSnapshot {
  const factor = kind === "research" ? 0.7 : 1;
  return {
    food: Math.round(180 * level * factor),
    wood: Math.round(140 * level * factor),
    stone: Math.round(90 * level * factor),
    iron: Math.round(45 * level * factor),
  };
}

function canAfford(resources: GameResourceSnapshot, cost: GameResourceSnapshot): boolean {
  return RESOURCE_KEYS.every((key) => resources[key] >= cost[key]);
}

function spend(resources: GameResourceSnapshot, cost: GameResourceSnapshot): GameResourceSnapshot {
  const next = cloneResources(resources);
  for (const key of RESOURCE_KEYS) next[key] -= cost[key];
  return next;
}

function resourceProduction(buildings: GameBuildingSnapshot[], research: GameResearchSnapshot[]): GameResourceSnapshot {
  const lumberLevel = buildings.find((item) => item.id === "lumber-mill")?.level ?? 1;
  const agricultureLevel = research.find((item) => item.id === "agriculture")?.level ?? 0;
  const masonryLevel = research.find((item) => item.id === "masonry")?.level ?? 0;
  return {
    food: 360 + agricultureLevel * 70,
    wood: 300 + lumberLevel * 90,
    stone: 180 + masonryLevel * 45,
    iron: 90 + masonryLevel * 22,
  };
}

function armyPower(army: GameArmySnapshot, militaryLevel: number): number {
  return army.scout * 6 + army.infantry * (10 + militaryLevel * 2) +
    army.cavalry * (24 + militaryLevel * 4) + army.archer * (16 + militaryLevel * 3);
}

function territoryCoordinates(userId: number): { mapX: number; mapY: number } {
  const normalized = Math.abs(userId);
  return {
    mapX: (normalized % 5) + 1,
    mapY: (Math.floor(normalized / 5) % 4) + 1,
  };
}

function accruedResources(kingdom: GameKingdom, now = Date.now()): GameResourceSnapshot {
  const production = resourceProduction(kingdom.buildings, kingdom.research);
  const elapsedHours = Math.max(0, (now - kingdom.lastCollectedAt.getTime()) / 3_600_000);
  const next = cloneResources(kingdom.resources);
  for (const key of RESOURCE_KEYS) {
    next[key] = Math.min(100_000, next[key] + Math.floor(production[key] * elapsedHours));
  }
  return next;
}

async function ensureKingdom(user: TelegramGameUser): Promise<GameKingdom> {
  const [existing] = await db.select().from(gameKingdomsTable).where(eq(gameKingdomsTable.telegramUserId, user.id));
  if (existing) {
    if (existing.name !== user.displayName) {
      const [updated] = await db
        .update(gameKingdomsTable)
        .set({ name: user.displayName, updatedAt: new Date() })
        .where(eq(gameKingdomsTable.telegramUserId, user.id))
        .returning();
      return updated ?? existing;
    }
    return existing;
  }

  const [created] = await db
    .insert(gameKingdomsTable)
    .values({
      telegramUserId: user.id,
      name: user.displayName,
      ...territoryCoordinates(user.id),
      resources: RESOURCE_SEED,
      buildings: BUILDING_SEED,
      research: RESEARCH_SEED,
      army: ARMY_SEED,
      discoveredTiles: ["capital"],
    })
    .onConflictDoNothing()
    .returning();
  if (created) return created;
  const [raced] = await db.select().from(gameKingdomsTable).where(eq(gameKingdomsTable.telegramUserId, user.id));
  if (!raced) throw new Error("Kingdom could not be initialized.");
  return raced;
}

async function ensureWorldEvent(): Promise<void> {
  const now = Date.now();
  await db.insert(gameWorldEventsTable).values({
    ...EVENT_SEED,
    startsAt: new Date(now - 3_600_000),
    endsAt: new Date(now + 6 * 24 * 3_600_000),
  }).onConflictDoNothing();
}

async function ensureDefaultAlliance(): Promise<void> {
  await db.insert(gameAlliancesTable).values({
    id: "alliance-ash",
    name: "Пепельный дозор",
    tag: "ASH",
    leaderId: 0,
    memberCount: 12,
    description: "Союз домов, которые держат границу, пока короли спорят о гербах.",
  }).onConflictDoNothing();
}

async function findMembership(userId: number) {
  const [membership] = await db
    .select()
    .from(gameAllianceMembersTable)
    .where(eq(gameAllianceMembersTable.telegramUserId, userId));
  return membership;
}

async function getAllianceSnapshot(userId: number) {
  const membership = await findMembership(userId);
  if (!membership) return null;
  const [alliance] = await db
    .select()
    .from(gameAlliancesTable)
    .where(eq(gameAlliancesTable.id, membership.allianceId));
  if (!alliance) return null;
  return {
    id: alliance.id,
    name: alliance.name,
    tag: alliance.tag,
    role: membership.role as "leader" | "officer" | "member",
    memberCount: alliance.memberCount,
    description: alliance.description,
  };
}

function tileSnapshot(kingdom: GameKingdom) {
  const discovered = new Set(kingdom.discoveredTiles);
  return WORLD_TILES.map((tile) => ({
    ...tile,
    ownerName: tile.id === "capital" ? kingdom.name : tile.kind === "player" ? "Лорд Эдгар" : null,
    ownerId: null,
    discovered: discovered.has(tile.id) || tile.id === "capital",
  }));
}

export async function getStrategyState(user: TelegramGameUser) {
  const kingdom = await ensureKingdom(user);
  await ensureWorldEvent();
  await ensureDefaultAlliance();
  const otherKingdoms = await db
    .select()
    .from(gameKingdomsTable)
    .where(sql`${gameKingdomsTable.telegramUserId} <> ${user.id}`)
    .limit(12);
  const militaryLevel = kingdom.research.find((item) => item.id === "military-doctrine")?.level ?? 0;
  const eventRows = await db.select().from(gameWorldEventsTable).orderBy(asc(gameWorldEventsTable.endsAt));
  const reports = await db
    .select()
    .from(gameBattleReportsTable)
    .where(eq(gameBattleReportsTable.attackerId, user.id))
    .orderBy(desc(gameBattleReportsTable.createdAt))
    .limit(5);
  const now = new Date();
  const events = eventRows.map((event) => ({
    id: event.id,
    title: event.title,
    description: event.description,
    progress: event.progress,
    goal: event.goal,
    endsAt: event.endsAt.toISOString(),
    reward: event.reward,
    status: event.endsAt < now ? "complete" as const : event.startsAt > now ? "upcoming" as const : "live" as const,
  }));

  return {
    kingdom: {
      name: kingdom.name,
      level: kingdom.cityLevel,
      power: kingdom.power,
      resources: accruedResources(kingdom),
      productionPerHour: resourceProduction(kingdom.buildings, kingdom.research),
      buildings: kingdom.buildings.map((building) => ({
        ...building,
        upgradeCost: resourceCost(building.level + 1, "building"),
      })),
      research: kingdom.research.map((item) => ({
        ...item,
        researchCost: resourceCost(item.level + 1, "research"),
      })),
      army: {
        ...kingdom.army,
        totalPower: armyPower(kingdom.army, militaryLevel),
      },
    },
    map: {
      centerX: kingdom.mapX,
      centerY: kingdom.mapY,
      tiles: [
        ...tileSnapshot(kingdom),
        ...otherKingdoms.map((other) => ({
          id: `player-${other.telegramUserId}`,
          x: other.mapX,
          y: other.mapY,
          label: other.name,
          terrain: "territory",
          kind: "player" as const,
          ownerName: other.name,
          ownerId: other.telegramUserId,
          power: other.power,
          reward: "захват влияния",
          discovered: kingdom.discoveredTiles.includes(`player-${other.telegramUserId}`),
        })),
      ],
    },
    alliance: await getAllianceSnapshot(user.id),
    events,
    reports: reports.map((report) => ({
      id: report.id,
      battleType: report.battleType as "scout" | "npc" | "pvp",
      opponent: report.opponent,
      result: report.result as "victory" | "defeat" | "discovered",
      powerDelta: report.powerDelta,
      reward: report.reward,
      createdAt: report.createdAt.toISOString(),
    })),
    onlinePlayers: otherKingdoms.length + 1,
    serverTime: now.toISOString(),
  };
}

async function updateKingdom(userId: number, patch: Partial<typeof gameKingdomsTable.$inferInsert>): Promise<void> {
  await db.update(gameKingdomsTable).set({ ...patch, updatedAt: new Date() }).where(eq(gameKingdomsTable.telegramUserId, userId));
}

export async function performStrategyCommand(user: TelegramGameUser, command: StrategyCommand) {
  if (command.quantity !== undefined && (!Number.isSafeInteger(command.quantity) || command.quantity < 1 || command.quantity > 1000)) {
    throw new StrategyRuleError("Количество должно быть целым числом от 1 до 1000.");
  }

  const kingdom = await ensureKingdom(user);
  const resources = accruedResources(kingdom);
  const buildings = kingdom.buildings.map((item) => ({ ...item }));
  const research = kingdom.research.map((item) => ({ ...item }));
  const army = { ...kingdom.army };
  let power = kingdom.power;

  switch (command.action) {
    case "collect_resources":
      await updateKingdom(user.id, { resources, lastCollectedAt: new Date() });
      break;

    case "upgrade_building": {
      const building = buildings.find((item) => item.id === command.targetId);
      if (!building) throw new StrategyRuleError("Такого здания нет в городе.");
      const cost = resourceCost(building.level + 1, "building");
      if (!canAfford(resources, cost)) throw new StrategyRuleError("Не хватает ресурсов для улучшения.");
      const next = buildings.map((item) => item.id === building.id ? { ...item, level: item.level + 1 } : item);
      await updateKingdom(user.id, {
        resources: spend(resources, cost),
        lastCollectedAt: new Date(),
        buildings: next,
        cityLevel: next.find((item) => item.id === "city-hall")?.level ?? kingdom.cityLevel,
        power: power + 35 + building.level * 15,
      });
      break;
    }

    case "research": {
      const item = research.find((entry) => entry.id === command.targetId);
      if (!item) throw new StrategyRuleError("Такого исследования нет в академии.");
      const cost = resourceCost(item.level + 1, "research");
      if (!canAfford(resources, cost)) throw new StrategyRuleError("Не хватает ресурсов для исследования.");
      await updateKingdom(user.id, {
        resources: spend(resources, cost),
        lastCollectedAt: new Date(),
        research: research.map((entry) => entry.id === item.id ? { ...entry, level: entry.level + 1 } : entry),
        power: power + 50 + item.level * 20,
      });
      break;
    }

    case "train_army": {
      const unit = command.targetId as keyof GameArmySnapshot;
      if (!["scout", "infantry", "cavalry", "archer"].includes(unit)) throw new StrategyRuleError("Неизвестный тип войск.");
      const quantity = command.quantity ?? 1;
      const cost = {
        food: quantity * (unit === "scout" ? 12 : unit === "infantry" ? 20 : unit === "cavalry" ? 42 : 30),
        wood: quantity * (unit === "archer" ? 18 : 8),
        stone: 0,
        iron: quantity * (unit === "cavalry" ? 16 : unit === "infantry" ? 5 : 3),
      };
      if (!canAfford(resources, cost)) throw new StrategyRuleError("Не хватает ресурсов для обучения отряда.");
      const nextArmy = { ...army, [unit]: army[unit] + quantity };
      await updateKingdom(user.id, { resources: spend(resources, cost), lastCollectedAt: new Date(), army: nextArmy, power: power + quantity * 8 });
      break;
    }

    case "scout": {
      const tile = WORLD_TILES.find((item) => item.id === command.targetId);
      if (!tile) throw new StrategyRuleError("Точка на карте не найдена.");
      if (kingdom.discoveredTiles.includes(tile.id)) return getStrategyState(user);
      await updateKingdom(user.id, { discoveredTiles: [...kingdom.discoveredTiles, tile.id] });
      await db.insert(gameBattleReportsTable).values({
        id: randomUUID(),
        attackerId: user.id,
        battleType: "scout",
        opponent: tile.label,
        result: "discovered",
        powerDelta: 0,
        reward: tile.reward ?? "новые сведения",
      });
      break;
    }

    case "attack_npc": {
      const tile = WORLD_TILES.find((item) => item.id === command.targetId && item.kind === "npc");
      if (!tile) throw new StrategyRuleError("Цель NPC не найдена.");
      const militaryLevel = research.find((item) => item.id === "military-doctrine")?.level ?? 0;
      const playerPower = armyPower(army, militaryLevel);
      const won = playerPower >= tile.power;
      const loss = won ? Math.max(1, Math.floor(army.infantry * 0.08)) : Math.max(2, Math.floor(army.infantry * 0.24));
      const nextArmy = { ...army, infantry: Math.max(0, army.infantry - loss) };
      const nextResources = won ? { ...resources, wood: resources.wood + 250, food: resources.food + 80 } : resources;
      await updateKingdom(user.id, {
        resources: nextResources,
        lastCollectedAt: new Date(),
        army: nextArmy,
        power: Math.max(0, power + (won ? 120 : -35)),
        discoveredTiles: [...new Set([...kingdom.discoveredTiles, tile.id])],
      });
      await db.insert(gameBattleReportsTable).values({
        id: randomUUID(),
        attackerId: user.id,
        battleType: "npc",
        opponent: tile.label,
        result: won ? "victory" : "defeat",
        powerDelta: won ? 120 : -35,
        reward: won ? tile.reward ?? "трофеи" : "отряд отступил",
      });
      break;
    }

    case "attack_player": {
      const targetMatch = command.targetId?.match(/^player-(\d+)$/);
      const defenderId = targetMatch ? Number(targetMatch[1]) : Number.NaN;
      if (!Number.isSafeInteger(defenderId) || defenderId === user.id) {
        throw new StrategyRuleError("Выбери владение другого игрока.");
      }
      const [defender] = await db.select().from(gameKingdomsTable).where(eq(gameKingdomsTable.telegramUserId, defenderId));
      if (!defender) throw new StrategyRuleError("Это владение больше не найдено.");
      const playerPower = armyPower(army, research.find((item) => item.id === "military-doctrine")?.level ?? 0);
      const won = playerPower > defender.power;
      const loss = won ? Math.max(1, Math.floor(army.infantry * 0.12)) : Math.max(2, Math.floor(army.infantry * 0.28));
      await updateKingdom(user.id, {
        army: { ...army, infantry: Math.max(0, army.infantry - loss) },
        power: Math.max(0, power + (won ? 180 : -50)),
        discoveredTiles: [...new Set([...kingdom.discoveredTiles, `player-${defenderId}`])],
      });
      if (won) {
        await db.update(gameKingdomsTable).set({ power: Math.max(0, defender.power - 80), updatedAt: new Date() }).where(eq(gameKingdomsTable.telegramUserId, defenderId));
      }
      await db.insert(gameBattleReportsTable).values({
        id: randomUUID(),
        attackerId: user.id,
        battleType: "pvp",
        opponent: defender.name,
        result: won ? "victory" : "defeat",
        powerDelta: won ? 180 : -50,
        reward: won ? "влияние на пограничном тракте" : "войско отступило",
      });
      break;
    }

    case "create_alliance": {
      const name = command.name?.trim();
      const tag = command.tag?.trim().toUpperCase();
      if (!name || !tag) throw new StrategyRuleError("Укажи название и короткий тег альянса.");
      if (!/^[A-ZА-ЯЁ0-9]{2,6}$/.test(tag)) throw new StrategyRuleError("Тег должен содержать 2–6 букв или цифр.");
      if (await findMembership(user.id)) throw new StrategyRuleError("Ты уже состоишь в альянсе.");
      const id = `alliance-${randomUUID()}`;
      try {
        await db.transaction(async (tx) => {
          await tx.insert(gameAlliancesTable).values({ id, name, tag, leaderId: user.id, memberCount: 1 });
          await tx.insert(gameAllianceMembersTable).values({ allianceId: id, telegramUserId: user.id, role: "leader" });
        });
      } catch {
        throw new StrategyRuleError("Этот тег альянса уже занят.");
      }
      break;
    }

    case "join_alliance": {
      if (!command.targetId) throw new StrategyRuleError("Выбери альянс для вступления.");
      if (await findMembership(user.id)) throw new StrategyRuleError("Сначала выйди из текущего альянса.");
      const [alliance] = await db.select().from(gameAlliancesTable).where(eq(gameAlliancesTable.id, command.targetId));
      if (!alliance) throw new StrategyRuleError("Альянс не найден.");
      await db.transaction(async (tx) => {
        await tx.insert(gameAllianceMembersTable).values({ allianceId: alliance.id, telegramUserId: user.id, role: "member" });
        await tx.update(gameAlliancesTable).set({ memberCount: sql`${gameAlliancesTable.memberCount} + 1` }).where(eq(gameAlliancesTable.id, alliance.id));
      });
      break;
    }

    case "leave_alliance": {
      const membership = await findMembership(user.id);
      if (!membership) throw new StrategyRuleError("Ты не состоишь в альянсе.");
      const [alliance] = await db.select().from(gameAlliancesTable).where(eq(gameAlliancesTable.id, membership.allianceId));
      if (alliance?.leaderId === user.id) throw new StrategyRuleError("Лидер должен сначала передать корону.");
      await db.delete(gameAllianceMembersTable).where(and(
        eq(gameAllianceMembersTable.allianceId, membership.allianceId),
        eq(gameAllianceMembersTable.telegramUserId, user.id),
      ));
      await db.update(gameAlliancesTable).set({ memberCount: sql`greatest(1, ${gameAlliancesTable.memberCount} - 1)` }).where(eq(gameAlliancesTable.id, membership.allianceId));
      break;
    }

    case "contribute_event": {
      if (!command.targetId) throw new StrategyRuleError("Выбери мировое событие.");
      const [event] = await db.select().from(gameWorldEventsTable).where(eq(gameWorldEventsTable.id, command.targetId));
      if (!event || event.endsAt < new Date()) throw new StrategyRuleError("Это событие уже завершено.");
      const cost = { food: 80, wood: 50, stone: 20, iron: 0 };
      if (!canAfford(resources, cost)) throw new StrategyRuleError("Не хватает ресурсов для вклада.");
      await db.transaction(async (tx) => {
        await tx.update(gameKingdomsTable)
          .set({ resources: spend(resources, cost), lastCollectedAt: new Date(), updatedAt: new Date() })
          .where(eq(gameKingdomsTable.telegramUserId, user.id));
        await tx.update(gameWorldEventsTable)
          .set({ progress: sql`least(${gameWorldEventsTable.goal}, ${gameWorldEventsTable.progress} + 1)` })
          .where(eq(gameWorldEventsTable.id, event.id));
      });
      break;
    }
  }

  return getStrategyState(user);
}