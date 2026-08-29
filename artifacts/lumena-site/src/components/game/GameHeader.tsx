import { Coins, Flame, Home, RefreshCw, ShieldCheck, Sparkles } from 'lucide-react';
import { Link } from 'wouter';
import type { GameStatePlayer } from '@workspace/api-client-react';

interface GameHeaderProps {
  player: GameStatePlayer;
  streak: number;
  insideTelegram: boolean;
  isRefreshing: boolean;
  onRefresh: () => void;
}

export function GameHeader({ player, streak, insideTelegram, isRefreshing, onRefresh }: GameHeaderProps) {
  const xpPercent = Math.min(100, Math.round((player.xp / player.xpToNext) * 100));

  return (
    <header className="game-header">
      <Link href="/" className="game-brand" data-testid="link-lumena-home">
        <span className="game-brand-mark"><Sparkles size={16} strokeWidth={2.5} /></span>
        <span>
          <strong>Лумена</strong>
          <small>Котострой</small>
        </span>
      </Link>

      <div className="game-player" data-testid="text-player-summary">
        <div className="game-avatar">{player.displayName.slice(0, 1).toUpperCase()}</div>
        <div className="game-player-copy">
          <div className="game-player-name">{player.displayName}</div>
          <div className="game-level-line">
            <span>уровень {player.level}</span>
            <span className="game-xp-track"><span style={{ width: `${xpPercent}%` }} /></span>
            <span>{player.xp} / {player.xpToNext} XP</span>
          </div>
        </div>
      </div>

      <div className="game-header-actions">
        <div className="game-stat-pill" data-testid="text-streak">
          <Flame size={15} />
          <span>{streak} дней</span>
        </div>
        <div className="game-stat-pill game-coin-pill" data-testid="text-game-lmn">
          <Coins size={15} />
          <span>{player.gameLmn.toLocaleString('ru-RU')} LMN</span>
        </div>
        <button
          type="button"
          className="game-icon-button"
          onClick={onRefresh}
          disabled={isRefreshing || !insideTelegram}
          aria-label="Обновить состояние"
          data-testid="button-refresh-game"
        >
          <RefreshCw size={17} className={isRefreshing ? 'game-spin' : ''} />
        </button>
        <Link href="/" className="game-icon-button game-home-button" aria-label="На главную" data-testid="link-game-home">
          <Home size={17} />
        </Link>
      </div>

      {!insideTelegram && (
        <div className="game-preview-chip" data-testid="status-telegram-preview">
          <ShieldCheck size={14} />
          <span>режим предпросмотра</span>
        </div>
      )}
    </header>
  );
}