import { ArrowUpRight, Check, CircleDashed, Coins, Gift, Hammer, LockKeyhole, Play, Sparkles } from 'lucide-react';
import type { GameLocation, GameQuest } from '@workspace/api-client-react';

interface GameQuestPanelProps {
  quests: GameQuest[];
  locations: GameLocation[];
  selectedLocationId: string | null;
  featuredQuestId: string | null;
  isPending: boolean;
  previewMode: boolean;
  onStart: (quest: GameQuest) => void;
  onClaim: (quest: GameQuest) => void;
}

function statusLabel(status: GameQuest['status']) {
  return {
    locked: 'закрыто',
    available: 'доступно',
    in_progress: 'в процессе',
    completed: 'готово',
    claimed: 'получено',
  }[status];
}

export function GameQuestPanel({
  quests,
  locations,
  selectedLocationId,
  featuredQuestId,
  isPending,
  previewMode,
  onStart,
  onClaim,
}: GameQuestPanelProps) {
  const selectedLocation = locations.find((location) => location.id === selectedLocationId);
  const visibleQuests = quests.filter((quest) => !selectedLocationId || quest.locationId === selectedLocationId);
  const fallbackQuests = visibleQuests.length ? visibleQuests : quests;

  return (
    <aside className="quest-panel" aria-labelledby="quest-heading">
      <div className="quest-panel-topline">
        <div className="section-kicker"><span className="kicker-dot accent-dot" /> дело на сегодня</div>
        <span className="quest-count">{quests.filter((quest) => quest.status !== 'claimed').length} активных</span>
      </div>
      <div className="quest-heading-row">
        <div>
          <h2 id="quest-heading">{selectedLocation ? selectedLocation.title : 'Первые шаги'}</h2>
          <p>{selectedLocation?.description || 'Небольшое дело, с которого начинается большой город.'}</p>
        </div>
        <div className="quest-compass-mark"><Hammer size={19} /></div>
      </div>

      <div className="quest-list">
        {fallbackQuests.length === 0 && (
          <div className="game-empty-state" data-testid="empty-quests">
            <CircleDashed size={25} />
            <strong>Тихий район</strong>
            <span>Здесь пока нет заданий. Загляни в соседний квартал.</span>
          </div>
        )}
        {fallbackQuests.map((quest) => {
          const isFeatured = featuredQuestId === quest.id;
          const progress = Math.min(100, Math.round((quest.progress / quest.goal) * 100));
          const canStart = quest.status === 'available';
          const canClaim = quest.status === 'completed';
          const location = locations.find((item) => item.id === quest.locationId);
          return (
            <article className={`quest-card ${isFeatured ? 'is-featured' : ''} status-${quest.status}`} key={quest.id} data-testid={`card-quest-${quest.id}`}>
              {isFeatured && <div className="featured-label"><Sparkles size={12} /> рекомендуем</div>}
              <div className="quest-card-heading">
                <div className="quest-card-icon" style={{ background: location?.accent || '#f47b53' }}>
                  {quest.status === 'claimed' ? <Check size={17} /> : quest.status === 'locked' ? <LockKeyhole size={16} /> : <Hammer size={17} />}
                </div>
                <div className="quest-card-title-wrap">
                  <h3>{quest.title}</h3>
                  <span>{location?.title || 'город'}</span>
                </div>
                <span className={`quest-status status-${quest.status}`}>{statusLabel(quest.status)}</span>
              </div>
              <p className="quest-description">{quest.description}</p>
              <div className="quest-progress-row">
                <div className="quest-progress-track"><span style={{ width: `${progress}%` }} /></div>
                <strong>{quest.progress} <small>/ {quest.goal}</small></strong>
              </div>
              <div className="quest-card-footer">
                <div className="quest-reward"><Coins size={15} /><span>+{quest.rewardLmn} LMN</span></div>
                {canStart && (
                  <button type="button" className="game-action-button" onClick={() => onStart(quest)} disabled={isPending} data-testid={`button-start-quest-${quest.id}`}>
                    <Play size={14} fill="currentColor" /> начать
                  </button>
                )}
                {canClaim && (
                  <button type="button" className="game-action-button claim-button" onClick={() => onClaim(quest)} disabled={isPending} data-testid={`button-claim-quest-${quest.id}`}>
                    <Gift size={14} /> забрать
                  </button>
                )}
                {quest.status === 'in_progress' && <span className="quest-in-progress"><span /> строим...</span>}
                {quest.status === 'claimed' && <span className="quest-claimed"><Check size={14} /> награда получена</span>}
                {quest.status === 'locked' && <span className="quest-locked"><ArrowUpRight size={14} /> открой район</span>}
              </div>
            </article>
          );
        })}
      </div>

      {previewMode && (
        <div className="preview-note"><Sparkles size={14} /><span>В предпросмотре действия работают локально — открой в Telegram, чтобы сохранить прогресс.</span></div>
      )}
    </aside>
  );
}