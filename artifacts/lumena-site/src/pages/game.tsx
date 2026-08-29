import { AlertTriangle, Check, LoaderCircle, RefreshCw, Sparkles } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useClaimGameQuest, useGetGameState, useStartGameQuest } from '@workspace/api-client-react';
import type { GameQuest, GameState } from '@workspace/api-client-react';
import { GameHeader } from '@/components/game/GameHeader';
import { GameMap } from '@/components/game/GameMap';
import { GameQuestPanel } from '@/components/game/GameQuestPanel';
import { isInsideTelegram, useTelegramWebApp } from '@/hooks/useTelegramWebApp';

const previewState: GameState = {
  player: { displayName: 'Гость Лумены', level: 4, xp: 260, xpToNext: 500, gameLmn: 1240 },
  streak: 3,
  featuredQuestId: 'welcome-build',
  locations: [
    { id: 'harbor', title: 'Тихая пристань', description: 'Здесь город встречает море и первые идеи.', state: 'available', accent: '#f47b53' },
    { id: 'market', title: 'Мяу-маркет', description: 'Маленькие лавки для больших находок.', state: 'discovered', accent: '#75c9b0' },
    { id: 'observatory', title: 'Чердачная башня', description: 'Самая высокая точка района.', state: 'locked', accent: '#e8bd68' },
  ],
  quests: [
    { id: 'welcome-build', title: 'Поставить первый фонарь', description: 'Город любит, когда в нём становится светлее. Начни с одного фонаря у пристани.', locationId: 'harbor', rewardLmn: 80, progress: 0, goal: 1, status: 'available' },
    { id: 'market-scout', title: 'Заглянуть на рынок', description: 'Познакомься с соседями и найди место для будущей лавки.', locationId: 'market', rewardLmn: 120, progress: 1, goal: 1, status: 'completed' },
    { id: 'tower-plan', title: 'Эскиз башни', description: 'Нужен новый уровень, чтобы подняться на чердак.', locationId: 'observatory', rewardLmn: 240, progress: 0, goal: 2, status: 'locked' },
  ],
};

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <main className="game-page game-centered-state">
      <div className="game-state-card error-state" data-testid="status-game-error">
        <div className="state-icon"><AlertTriangle size={24} /></div>
        <div className="section-kicker">связь с городом потеряна</div>
        <h1>Лумка не отвечает</h1>
        <p>Попробуй обновить игру. Прогресс не пропадёт.</p>
        <button type="button" className="game-primary-button" onClick={onRetry} data-testid="button-retry-game"><RefreshCw size={16} /> повторить</button>
      </div>
    </main>
  );
}

function LoadingState() {
  return (
    <main className="game-page">
      <div className="game-skeleton-header"><span /><span /><span /></div>
      <div className="game-loading-grid">
        <div className="game-skeleton-map"><div className="skeleton-shimmer" /></div>
        <div className="game-skeleton-quests"><div className="skeleton-shimmer" /><div className="skeleton-shimmer short" /><div className="skeleton-shimmer card" /></div>
      </div>
      <div className="loading-caption"><LoaderCircle size={16} className="game-spin" /> загружаем город</div>
    </main>
  );
}

export default function GamePage() {
  const tg = useTelegramWebApp();
  const telegramAvailable = isInsideTelegram();
  const initData = tg?.initData ?? '';
  const [gameState, setGameState] = useState<GameState | null>(telegramAvailable ? null : previewState);
  const [selectedLocationId, setSelectedLocationId] = useState<string | null>(previewState.locations[0]?.id ?? null);
  const [hasLoaded, setHasLoaded] = useState(!telegramAvailable);
  const getGameState = useGetGameState();
  const startGameQuest = useStartGameQuest();
  const claimGameQuest = useClaimGameQuest();
  const getStateRef = useRef(getGameState.mutate);
  getStateRef.current = getGameState.mutate;

  const loadState = useCallback(() => {
    if (!initData) {
      setGameState(previewState);
      setHasLoaded(true);
      return;
    }
    setHasLoaded(false);
    getStateRef.current({ data: { initData } }, {
      onSuccess: (nextState) => {
        setGameState(nextState);
        setSelectedLocationId(nextState.locations.find((location) => location.state !== 'locked')?.id ?? null);
        setHasLoaded(true);
      },
      onError: () => setHasLoaded(true),
    });
  }, [initData]);

  useEffect(() => { loadState(); }, [loadState]);

  const selectedLocationIdRef = useRef(selectedLocationId);
  selectedLocationIdRef.current = selectedLocationId;
  const activeLocation = useMemo(
    () => gameState?.locations.find((location) => location.id === selectedLocationId) ?? gameState?.locations.find((location) => location.state !== 'locked'),
    [gameState, selectedLocationId],
  );

  const applyPreviewQuestChange = (quest: GameQuest, action: 'start' | 'claim') => {
    setGameState((current) => {
      if (!current) return current;
      const quests = current.quests.map((item) => {
        if (item.id !== quest.id) return item;
        if (action === 'start') return { ...item, progress: item.goal, status: 'completed' as const };
        return { ...item, status: 'claimed' as const };
      });
      const nextQuest = action === 'claim'
        ? quests.find((item) => item.id === quest.id)
        : undefined;
      return {
        ...current,
        quests,
        player: action === 'claim' && nextQuest ? { ...current.player, gameLmn: current.player.gameLmn + quest.rewardLmn, xp: current.player.xp + 40 } : current.player,
      };
    });
  };

  const handleStart = (quest: GameQuest) => {
    if (!initData) {
      applyPreviewQuestChange(quest, 'start');
      return;
    }
    startGameQuest.mutate({ questId: quest.id, data: { initData } }, { onSuccess: setGameState });
  };

  const handleClaim = (quest: GameQuest) => {
    if (!initData) {
      applyPreviewQuestChange(quest, 'claim');
      return;
    }
    claimGameQuest.mutate({ questId: quest.id, data: { initData } }, { onSuccess: setGameState });
  };

  if (telegramAvailable && !hasLoaded && !getGameState.isError) return <LoadingState />;
  if (telegramAvailable && getGameState.isError && !gameState) return <ErrorState onRetry={loadState} />;
  if (!gameState) return <ErrorState onRetry={loadState} />;

  const isPending = startGameQuest.isPending || claimGameQuest.isPending;
  return (
    <main className="game-page">
      <div className="game-ambient-orb orb-one" />
      <div className="game-ambient-orb orb-two" />
      <GameHeader player={gameState.player} streak={gameState.streak} insideTelegram={telegramAvailable} isRefreshing={getGameState.isPending} onRefresh={loadState} />
      {!telegramAvailable && (
        <div className="game-preview-banner" data-testid="banner-preview-mode">
          <Sparkles size={16} />
          <span><strong>Сейчас вы в предпросмотре.</strong> Открой игру в Telegram, чтобы твой город и награды сохранялись.</span>
        </div>
      )}
      <div className="game-layout">
        <GameMap locations={gameState.locations} selectedLocationId={activeLocation?.id ?? selectedLocationIdRef.current} onSelectLocation={(location) => setSelectedLocationId(location.id)} />
        <GameQuestPanel
          quests={gameState.quests}
          locations={gameState.locations}
          selectedLocationId={activeLocation?.id ?? null}
          featuredQuestId={gameState.featuredQuestId}
          isPending={isPending}
          previewMode={!telegramAvailable}
          onStart={handleStart}
          onClaim={handleClaim}
        />
      </div>
      <footer className="game-footer"><span>Лумена · Котострой</span><span>город строится маленькими делами</span><span className="footer-live"><Check size={12} /> сервис работает</span></footer>
    </main>
  );
}