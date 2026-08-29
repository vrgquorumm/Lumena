import { Router, type IRouter, type Request, type Response } from "express";
import {
  ClaimGameQuestBody,
  ClaimGameQuestParams,
  ClaimGameQuestResponse,
  ErrorResponse,
  GetGameStateBody,
  GetGameStateResponse,
  StartGameQuestBody,
  StartGameQuestParams,
  StartGameQuestResponse,
} from "@workspace/api-zod";
import { GameAuthError, validateTelegramInitData } from "../lib/game-auth";
import { GameRuleError, claimQuest, loadGameState, startQuest } from "../lib/game-service";

const router: IRouter = Router();

function authenticate(req: Request, res: Response, initData: string) {
  try {
    return validateTelegramInitData(initData);
  } catch (error) {
    if (error instanceof GameAuthError) {
      res.status(error.statusCode).json({ error: error.message });
      return null;
    }
    throw error;
  }
}

function handleGameError(req: Request, res: Response, error: unknown): void {
  if (error instanceof GameRuleError) {
    res.status(error.statusCode).json({ error: error.message });
    return;
  }
  req.log.error({ err: error }, "Game request failed");
  res.status(500).json({ error: "Игровой сервер временно недоступен." });
}

router.post("/game/state", async (req, res): Promise<void> => {
  const parsed = GetGameStateBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }
  const user = authenticate(req, res, parsed.data.initData);
  if (!user) return;
  try {
    res.json(GetGameStateResponse.parse(await loadGameState(user)));
  } catch (error) {
    handleGameError(req, res, error);
  }
});

router.post("/game/quests/:questId/start", async (req, res): Promise<void> => {
  const params = StartGameQuestParams.safeParse(req.params);
  const body = StartGameQuestBody.safeParse(req.body);
  if (!params.success || !body.success) {
    res.status(400).json({ error: "Некорректные данные задания." });
    return;
  }
  const user = authenticate(req, res, body.data.initData);
  if (!user) return;
  try {
    res.json(StartGameQuestResponse.parse(await startQuest(user, params.data.questId)));
  } catch (error) {
    handleGameError(req, res, error);
  }
});

router.post("/game/quests/:questId/claim", async (req, res): Promise<void> => {
  const params = ClaimGameQuestParams.safeParse(req.params);
  const body = ClaimGameQuestBody.safeParse(req.body);
  if (!params.success || !body.success) {
    res.status(400).json({ error: "Некорректные данные задания." });
    return;
  }
  const user = authenticate(req, res, body.data.initData);
  if (!user) return;
  try {
    res.json(ClaimGameQuestResponse.parse(await claimQuest(user, params.data.questId)));
  } catch (error) {
    handleGameError(req, res, error);
  }
});

export default router;