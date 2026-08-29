import {
  AlertTriangle, ArrowUpRight, Axe, BookOpen, Castle, Check, ChevronRight, CircleDot,
  Coins, Compass, Crown, Crosshair, Flame, Hammer, Landmark, LoaderCircle, Map as MapIcon,
  Medal, Minus, Pickaxe, Plus, RefreshCw, ScrollText, Shield, Sparkles, Swords, Users,
  Wheat, X,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  useClaimGameQuest, useGetGameState, usePerformGameCommand, useStartGameQuest,
} from '@workspace/api-client-react';
import type {
  GameAlliance, GameBattleReport, GameBuilding, GameCommandInput, GameKingdom, GameLocation, GameMapTile,
  GameQuest, GameResearch, GameState, GameWorldEvent,
} from '@workspace/api-client-react';
import { isInsideTelegram, useTelegramWebApp } from '@/hooks/useTelegramWebApp';
import { Link } from 'wouter';

const previewState: GameState = {
  player: { displayName: 'Марек из Валь-Роана', level: 7, xp: 612, xpToNext: 1000, gameLmn: 1840 },
  streak: 6,
  featuredQuestId: 'watchtower-oath',
  locations: [
    { id: 'north-gate', title: 'Северные ворота', description: 'Старая дорога к землям, где туман не рассеивается даже днём.', state: 'discovered', accent: '#b86f45' },
    { id: 'ironwood', title: 'Железный бор', description: 'Плотный лес. В стволах проступает руда цвета старого вина.', state: 'available', accent: '#557d68' },
    { id: 'salt-marsh', title: 'Солёные топи', description: 'Разведчики слышат там колокола под водой.', state: 'available', accent: '#6d8791' },
    { id: 'old-keep', title: 'Старая крепость', description: 'Здесь начиналась династия. Теперь стены заняты воронами.', state: 'locked', accent: '#8f8068' },
  ],
  quests: [
    { id: 'watchtower-oath', title: 'Клятва дозорного', description: 'Поставь дозор на северной дороге и узнай, кто оставляет следы у заставы.', locationId: 'north-gate', rewardLmn: 160, progress: 0, goal: 1, status: 'available' },
    { id: 'ironwood-route', title: 'Дорога через бор', description: 'Разведай Железный бор: королевству нужен безопасный путь к рудникам.', locationId: 'ironwood', rewardLmn: 220, progress: 1, goal: 2, status: 'in_progress' },
    { id: 'marsh-signal', title: 'Сигнал из топей', description: 'Найди источник колокольного звона до наступления прилива.', locationId: 'salt-marsh', rewardLmn: 310, progress: 0, goal: 1, status: 'completed' },
    { id: 'old-keep', title: 'Ворота предков', description: 'Собери достаточно силы, чтобы открыть перевал к старой крепости.', locationId: 'old-keep', rewardLmn: 480, progress: 0, goal: 3, status: 'locked' },
  ],
  kingdom: {
    name: 'Валь-Роан', level: 5, power: 2860,
    resources: { food: 1260, wood: 840, stone: 590, iron: 310 },
    productionPerHour: { food: 240, wood: 165, stone: 90, iron: 48 },
    buildings: [
      { id: 'keep', name: 'Пограничная крепость', level: 4, description: 'Сердце обороны и место, где хранятся королевские печати.', upgradeCost: { food: 240, wood: 380, stone: 260, iron: 90 } },
      { id: 'sawmill', name: 'Лесопильня', level: 3, description: 'Превращает железный бор в стены и мосты.', upgradeCost: { food: 100, wood: 260, stone: 110, iron: 45 } },
      { id: 'granary', name: 'Зерновой двор', level: 3, description: 'Запасы переживут осаду, если считать их каждый вечер.', upgradeCost: { food: 180, wood: 160, stone: 100, iron: 30 } },
      { id: 'watch', name: 'Дозорная башня', level: 2, description: 'Её огонь виден дальше, чем слухи о войне.', upgradeCost: { food: 90, wood: 220, stone: 180, iron: 70 } },
    ],
    research: [
      { id: 'wayfinding', name: 'Звёздная навигация', level: 2, description: 'Разведчики возвращаются быстрее и видят больше карты.', researchCost: { food: 160, wood: 110, stone: 90, iron: 60 } },
      { id: 'masonry', name: 'Каменная кладка', level: 1, description: 'Укрепляет здания и добавляет мощь королевству.', researchCost: { food: 110, wood: 80, stone: 180, iron: 75 } },
      { id: 'fieldcraft', name: 'Полевой промысел', level: 0, description: 'Армия расходует меньше припасов на дальних переходах.', researchCost: { food: 230, wood: 120, stone: 70, iron: 90 } },
    ],
    army: { scout: 18, infantry: 82, cavalry: 24, archer: 46, totalPower: 2140 },
  },
  map: {
    centerX: 3, centerY: 2,
    tiles: [
      { id: 't-11', x: 1, y: 1, label: 'Туманный склон', terrain: 'туман', kind: 'ruins', ownerName: null, power: 0, reward: 'древняя карта', discovered: false },
      { id: 't-21', x: 2, y: 1, label: 'Северный тракт', terrain: 'дорога', kind: 'npc', ownerName: 'Разбойный двор', power: 720, reward: '120 железа', discovered: true },
      { id: 't-31', x: 3, y: 1, label: 'Каменный круг', terrain: 'руины', kind: 'ruins', ownerName: null, power: 0, reward: 'осколок печати', discovered: false },
      { id: 't-41', x: 4, y: 1, label: 'Зелёный увал', terrain: 'луг', kind: 'resource', ownerName: null, power: 0, reward: '240 пищи', discovered: true },
      { id: 't-51', x: 5, y: 1, label: 'Сторожевой мыс', terrain: 'скалы', kind: 'npc', ownerName: 'Дом Краг', power: 1120, reward: 'знак дома', discovered: false },
      { id: 't-12', x: 1, y: 2, label: 'Солёные топи', terrain: 'болото', kind: 'event', ownerName: null, power: 0, reward: 'слава', discovered: true },
      { id: 't-22', x: 2, y: 2, label: 'Железный бор', terrain: 'лес', kind: 'resource', ownerName: null, power: 0, reward: '140 железа', discovered: true },
      { id: 't-32', x: 3, y: 2, label: 'Валь-Роан', terrain: 'столица', kind: 'capital', ownerName: 'Марек из Валь-Роана', power: 2860, reward: 'сердце королевства', discovered: true },
      { id: 't-42', x: 4, y: 2, label: 'Речной брод', terrain: 'река', kind: 'player', ownerName: 'Элин Вейр', power: 1740, reward: null, discovered: true },
      { id: 't-52', x: 5, y: 2, label: 'Сломанная башня', terrain: 'руины', kind: 'ruins', ownerName: null, power: 0, reward: 'старая сталь', discovered: false },
      { id: 't-13', x: 1, y: 3, label: 'Лесная застава', terrain: 'лес', kind: 'npc', ownerName: 'Серые волки', power: 540, reward: '240 дерева', discovered: true },
      { id: 't-23', x: 2, y: 3, label: 'Медный ручей', terrain: 'река', kind: 'resource', ownerName: null, power: 0, reward: 'камень', discovered: true },
      { id: 't-33', x: 3, y: 3, label: 'Курган королей', terrain: 'степь', kind: 'ruins', ownerName: null, power: 0, reward: 'летопись', discovered: false },
      { id: 't-43', x: 4, y: 3, label: 'Вороний дозор', terrain: 'холм', kind: 'npc', ownerName: 'Дозор Керн', power: 920, reward: 'путь на восток', discovered: false },
      { id: 't-53', x: 5, y: 3, label: 'Сухой перевал', terrain: 'скалы', kind: 'resource', ownerName: null, power: 0, reward: 'камень', discovered: false },
      { id: 't-14', x: 1, y: 4, label: 'Пепельный край', terrain: 'пустошь', kind: 'ruins', ownerName: null, power: 0, reward: null, discovered: false },
      { id: 't-24', x: 2, y: 4, label: 'Южная пашня', terrain: 'поля', kind: 'resource', ownerName: null, power: 0, reward: '360 пищи', discovered: true },
      { id: 't-34', x: 3, y: 4, label: 'Каменный мост', terrain: 'мост', kind: 'player', ownerName: 'Дом Ренн', power: 1320, reward: null, discovered: false },
      { id: 't-44', x: 4, y: 4, label: 'Дальний лес', terrain: 'лес', kind: 'resource', ownerName: null, power: 0, reward: '240 дерева', discovered: false },
      { id: 't-54', x: 5, y: 4, label: 'Северная граница', terrain: 'туман', kind: 'event', ownerName: null, power: 0, reward: 'знамя союза', discovered: false },
    ],
  },
  alliance: { id: 'alliance-ash', name: 'Пепельный дозор', tag: 'ASH', role: 'officer', memberCount: 18, description: 'Союз домов, которые держат границу, пока короли спорят о гербах.' },
  events: [
    { id: 'marsh-bells', title: 'Колокола под водой', description: 'Топи просыпаются. Внеси припасы в общий караван, чтобы удержать южную переправу.', progress: 640, goal: 1000, endsAt: '2025-12-18T21:00:00.000Z', reward: 'Знамя Прилива и 420 LMN', status: 'live' },
    { id: 'winter-court', title: 'Зимний двор', description: 'Собери сведения о домах до того, как выпадет первый снег.', progress: 1, goal: 3, endsAt: '2026-01-04T21:00:00.000Z', reward: 'место в совете', status: 'upcoming' },
  ],
  reports: [
    { id: 'report-1', battleType: 'scout', opponent: 'Сломанная башня', result: 'discovered', powerDelta: 0, reward: 'открыт северный склон', createdAt: '2025-11-14T17:20:00.000Z' },
    { id: 'report-2', battleType: 'npc', opponent: 'Серые волки', result: 'victory', powerDelta: 180, reward: '240 дерева', createdAt: '2025-11-14T13:05:00.000Z' },
  ],
  onlinePlayers: 37,
  serverTime: '2025-11-14T18:00:00.000Z',
};

type CommandAction = GameCommandInput['action'];
type Notice = { kind: 'success' | 'error'; text: string };
type RealtimeStatus = 'connecting' | 'live' | 'fallback';

const resourceMeta = [
  { key: 'food', label: 'Провиант', icon: Wheat, tone: 'saffron' },
  { key: 'wood', label: 'Дерево', icon: Axe, tone: 'moss' },
  { key: 'stone', label: 'Камень', icon: Pickaxe, tone: 'slate' },
  { key: 'iron', label: 'Железо', icon: Shield, tone: 'wine' },
] as const;

function formatNumber(value: number) {
  return value.toLocaleString('ru-RU');
}

function findLocation(locations: GameLocation[], locationId: string) {
  return locations.find((location) => location.id === locationId);
}

function timeAgo(value: string) {
  const minutes = Math.max(1, Math.round((Date.now() - new Date(value).getTime()) / 60000));
  return minutes < 60 ? `${minutes} мин назад` : `${Math.round(minutes / 60)} ч назад`;
}

function LoadingState() {
  return <main className="game-page game-loading" data-testid="status-game-loading">
    <div className="loading-crest"><Castle size={28} /></div>
    <div className="loading-lines"><span /><span /><span /><span className="wide" /></div>
    <div className="loading-columns"><div /><div /></div>
    <div className="loading-caption"><LoaderCircle size={15} /> восстанавливаем летопись королевства</div>
  </main>;
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return <main className="game-page game-centered-state">
    <section className="game-state-card" data-testid="status-game-error">
      <div className="state-icon"><AlertTriangle size={25} /></div>
      <span className="eyebrow">связь с архивом потеряна</span>
      <h1>Летопись не отвечает</h1>
      <p>Проверь соединение и повтори попытку. Последнее сохранённое состояние не изменено.</p>
      <button type="button" className="button button-primary" onClick={onRetry} data-testid="button-retry-game"><RefreshCw size={15} /> повторить синхронизацию</button>
    </section>
  </main>;
}

function ResourceStrip({ kingdom, onCollect, pending }: { kingdom: GameKingdom; onCollect: () => void; pending: boolean }) {
  return <section className="resources-card" data-testid="panel-resources">
    <div className="section-head compact"><div><span className="eyebrow">казна и припасы</span><h2>Ресурсы королевства</h2></div><button type="button" className="button button-small button-gold" onClick={onCollect} disabled={pending} data-testid="button-collect-resources"><Sparkles size={14} /> {pending ? 'собираем' : 'собрать доход'}</button></div>
    <div className="resource-grid">
      {resourceMeta.map(({ key, label, icon: Icon, tone }) => <div className={`resource-item tone-${tone}`} key={key} data-testid={`resource-${key}`}>
        <span className="resource-icon"><Icon size={16} /></span><div><strong>{formatNumber(kingdom.resources[key])}</strong><span>{label}</span></div><small>+{formatNumber(kingdom.productionPerHour[key])}/ч</small>
      </div>)}
    </div>
  </section>;
}

function StatLine({ label, value, icon: Icon }: { label: string; value: string; icon: typeof Crown }) {
  return <div className="stat-line"><Icon size={15} /><span>{label}</span><strong>{value}</strong></div>;
}

function TileIcon({ kind }: { kind: GameMapTile['kind'] }) {
  if (kind === 'capital') return <Castle size={15} />;
  if (kind === 'npc') return <Swords size={14} />;
  if (kind === 'resource') return <Pickaxe size={14} />;
  if (kind === 'event') return <Flame size={14} />;
  if (kind === 'player') return <Crown size={14} />;
  return <ScrollText size={14} />;
}

function WorldMap({ tiles, selectedId, onSelect, onScout, onAttack, pending }: {
  tiles: GameMapTile[]; selectedId: string; onSelect: (tile: GameMapTile) => void; onScout: () => void; onAttack: () => void; pending: boolean;
}) {
  const selected = tiles.find((tile) => tile.id === selectedId) ?? tiles[0];
  const minX = Math.min(...tiles.map((tile) => tile.x));
  const minY = Math.min(...tiles.map((tile) => tile.y));
  return <section className="map-card" aria-labelledby="map-heading">
    <div className="map-card-head"><div><span className="eyebrow"><Compass size={12} /> мировая карта · сектор 03</span><h2 id="map-heading">Граница Валь-Роана</h2></div><div className="map-coordinates">X {selected?.x ?? 0} · Y {selected?.y ?? 0}</div></div>
    <div className="map-legend"><span><i className="legend-dot capital" /> столица</span><span><i className="legend-dot npc" /> чужая сила</span><span><i className="legend-dot resource" /> ресурс</span><span><i className="legend-dot fog" /> неизвестно</span></div>
    <div className="world-map" data-testid="map-world">
      <div className="map-grid-lines" aria-hidden="true" />
       {tiles.map((tile) => <button type="button" key={tile.id} className={`map-tile tile-${tile.kind} ${tile.discovered ? '' : 'undiscovered'} ${selected?.id === tile.id ? 'selected' : ''}`} style={{ gridColumn: tile.x - minX + 1, gridRow: tile.y - minY + 1 }} onClick={() => onSelect(tile)} aria-label={`${tile.label}, ${tile.discovered ? tile.terrain : 'не разведано'}`} data-testid={`button-map-tile-${tile.id}`}>
        <TileIcon kind={tile.kind} /><span>{tile.discovered ? tile.label : 'неизвестно'}</span>{tile.kind === 'capital' && <b>вы здесь</b>}
      </button>)}
      <span className="map-north">N</span>
    </div>
    {selected && <div className="tile-dossier" data-testid="panel-selected-tile">
      <div className={`tile-dossier-icon tile-${selected.kind}`}><TileIcon kind={selected.kind} /></div><div className="tile-dossier-copy"><span className="eyebrow">{selected.discovered ? selected.terrain : 'данные скрыты'} · {selected.kind === 'npc' ? 'вражеская позиция' : selected.kind === 'capital' ? 'ваша земля' : 'точка интереса'}</span><h3>{selected.discovered ? selected.label : 'Туман за перевалом'}</h3><p>{selected.discovered ? (selected.ownerName ? `${selected.ownerName} · мощь ${formatNumber(selected.power)}` : selected.reward ?? 'Разведчики не нашли следов') : 'Отправь дозор, чтобы открыть сведения об этом тайле.'}</p></div>
       <div className="tile-actions">{!selected.discovered && selected.kind !== 'capital' && <button type="button" className="button button-small button-ink" onClick={onScout} disabled={pending} data-testid="button-scout-tile"><Compass size={14} /> разведать</button>}{selected.discovered && (selected.kind === 'npc' || (selected.kind === 'player' && selected.ownerId != null)) && <button type="button" className="button button-small button-wine" onClick={onAttack} disabled={pending} data-testid="button-attack-tile"><Crosshair size={14} /> атаковать</button>}</div>
    </div>}
  </section>;
}

function Cost({ cost }: { cost: GameBuilding['upgradeCost'] }) {
  return <span className="cost-line">{resourceMeta.map(({ key, icon: Icon }) => <span key={key} className={cost[key] ? '' : 'zero-cost'}><Icon size={11} />{formatNumber(cost[key])}</span>)}</span>;
}

function Buildings({ buildings, onUpgrade, pending }: { buildings: GameBuilding[]; onUpgrade: (building: GameBuilding) => void; pending: boolean }) {
  return <section className="paper-panel" data-testid="panel-buildings"><div className="section-head"><div><span className="eyebrow"><Landmark size={12} /> городская застройка</span><h2>Камень и дерево</h2></div><span className="panel-count">{buildings.length} объекта</span></div><div className="building-list">{buildings.map((building) => <article className="building-row" key={building.id} data-testid={`card-building-${building.id}`}><div className="building-seal"><Landmark size={16} /></div><div className="building-copy"><div className="row-title"><h3>{building.name}</h3><span>ур. {building.level}</span></div><p>{building.description}</p><Cost cost={building.upgradeCost} /></div><button type="button" className="icon-action" onClick={() => onUpgrade(building)} disabled={pending} aria-label={`Улучшить ${building.name}`} data-testid={`button-upgrade-building-${building.id}`}><ArrowUpRight size={16} /></button></article>)}</div></section>;
}

function Research({ research, onResearch, pending }: { research: GameResearch[]; onResearch: (item: GameResearch) => void; pending: boolean }) {
  return <section className="paper-panel" data-testid="panel-research"><div className="section-head"><div><span className="eyebrow"><BookOpen size={12} /> библиотека границы</span><h2>Исследования</h2></div><span className="panel-count">{research.filter((item) => item.level > 0).length}/{research.length} открыто</span></div><div className="research-list">{research.map((item) => <article className="research-row" key={item.id} data-testid={`card-research-${item.id}`}><div className="research-level">{String(item.level).padStart(2, '0')}</div><div className="research-copy"><div className="row-title"><h3>{item.name}</h3><span>ур. {item.level}</span></div><p>{item.description}</p><Cost cost={item.researchCost} /></div><button type="button" className="button button-small button-outline" onClick={() => onResearch(item)} disabled={pending} data-testid={`button-research-${item.id}`}><BookOpen size={13} /> изучить</button></article>)}</div></section>;
}

function Army({ kingdom, onTrain, pending }: { kingdom: GameKingdom; onTrain: (unit: 'infantry' | 'archer' | 'cavalry') => void; pending: boolean }) {
  const units = [{ key: 'infantry' as const, label: 'Пехота', value: kingdom.army.infantry, icon: Shield }, { key: 'archer' as const, label: 'Лучники', value: kingdom.army.archer, icon: Crosshair }, { key: 'cavalry' as const, label: 'Конница', value: kingdom.army.cavalry, icon: Swords }];
  return <section className="army-panel" data-testid="panel-army"><div className="section-head"><div><span className="eyebrow"><Swords size={12} /> гарнизон</span><h2>Сила под знамёнами</h2></div><div className="power-badge"><Shield size={13} /> {formatNumber(kingdom.army.totalPower)} мощи</div></div><div className="army-total"><div className="army-figure"><div className="crest-large"><Crown size={24} /></div><div><strong>{formatNumber(kingdom.army.scout + kingdom.army.infantry + kingdom.army.archer + kingdom.army.cavalry)}</strong><span>воинов в строю</span></div></div><span className="army-scouts"><Compass size={13} /> {kingdom.army.scout} разведчиков</span></div><div className="unit-grid">{units.map(({ key, label, value, icon: Icon }) => <div className="unit-card" key={key}><span className="unit-icon"><Icon size={17} /></span><strong>{value}</strong><span>{label}</span><button type="button" onClick={() => onTrain(key)} disabled={pending} data-testid={`button-train-${key}`}><Plus size={13} /> обучить</button></div>)}</div></section>;
}

function AlliancePanel({ alliance, onCreate, onJoin, onLeave, pending }: { alliance: GameAlliance | null; onCreate: (name: string, tag: string) => void; onJoin: () => void; onLeave: () => void; pending: boolean }) {
  const [name, setName] = useState('Стражи северной кромки');
  const [tag, setTag] = useState('SNK');
  return <section className="paper-panel alliance-panel" data-testid="panel-alliance"><div className="section-head"><div><span className="eyebrow"><Users size={12} /> союз домов</span><h2>Альянс</h2></div>{alliance && <span className="online-mark"><CircleDot size={12} /> {alliance.memberCount} в сети</span>}</div>{alliance ? <div className="alliance-active"><div className="alliance-banner"><span className="alliance-monogram">{alliance.tag.slice(0, 3)}</span><div><strong>{alliance.name}</strong><span>[{alliance.tag}] · {alliance.role === 'leader' ? 'глава' : alliance.role === 'officer' ? 'офицер' : 'член'}</span></div><Crown size={16} /></div><p>{alliance.description}</p><button type="button" className="button button-quiet" onClick={onLeave} disabled={pending} data-testid="button-leave-alliance"><X size={14} /> покинуть союз</button></div> : <div className="alliance-empty"><p>У королевства пока нет знамени. Создай союз или присоединись к соседям.</p><div className="alliance-form"><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Название союза" aria-label="Название союза" data-testid="input-alliance-name" /><input value={tag} onChange={(event) => setTag(event.target.value.toUpperCase().slice(0, 6))} placeholder="Тег" aria-label="Тег союза" data-testid="input-alliance-tag" /><button type="button" className="button button-primary" onClick={() => onCreate(name, tag)} disabled={pending || name.trim().length < 3 || tag.trim().length < 2} data-testid="button-create-alliance"><Plus size={14} /> основать</button></div><button type="button" className="button button-outline full-width" onClick={onJoin} disabled={pending} data-testid="button-join-alliance"><Users size={14} /> вступить в Пепельный дозор</button></div>}</section>;
}

function EventPanel({ event, onContribute, pending }: { event: GameWorldEvent | undefined; onContribute: () => void; pending: boolean }) {
  if (!event) return <section className="paper-panel empty-panel" data-testid="empty-events"><Flame size={22} /><h2>События стихают</h2><p>На границе пока спокойно. Это ненадолго.</p></section>;
  const progress = Math.min(100, Math.round((event.progress / event.goal) * 100));
  return <section className="event-panel" data-testid={`panel-event-${event.id}`}><div className="event-topline"><span className="eyebrow"><Flame size={12} /> мировое событие · {event.status === 'live' ? 'идёт сейчас' : 'скоро'}</span><span className="event-timer">{event.status === 'live' ? 'до заката' : 'готовится'}</span></div><h2>{event.title}</h2><p>{event.description}</p><div className="event-progress"><div><span>общий вклад</span><strong>{formatNumber(event.progress)} <small>/ {formatNumber(event.goal)}</small></strong></div><div className="progress-track"><span style={{ width: `${progress}%` }} /></div></div><div className="event-bottom"><span><Medal size={14} /> {event.reward}</span><button type="button" className="button button-gold" onClick={onContribute} disabled={pending || event.status !== 'live'} data-testid="button-contribute-event"><Plus size={14} /> внести 50</button></div></section>;
}

function QuestPanel({ state, onStart, onClaim, pending }: { state: GameState; onStart: (quest: GameQuest) => void; onClaim: (quest: GameQuest) => void; pending: boolean }) {
  return <section className="paper-panel quests-panel" data-testid="panel-quests"><div className="section-head"><div><span className="eyebrow"><ScrollText size={12} /> журнал поручений</span><h2>Задания границы</h2></div><span className="panel-count">{state.quests.filter((quest) => quest.status !== 'claimed').length} активных</span></div><div className="quest-list">{state.quests.length === 0 ? <div className="empty-inline">Новых поручений нет. Разведай карту, чтобы открыть следующую запись.</div> : state.quests.map((quest) => { const location = findLocation(state.locations, quest.locationId); const progress = Math.min(100, Math.round((quest.progress / quest.goal) * 100)); return <article className={`quest-row ${state.featuredQuestId === quest.id ? 'featured' : ''}`} key={quest.id} data-testid={`card-quest-${quest.id}`}><div className="quest-number">{quest.status === 'claimed' ? <Check size={15} /> : String(quest.progress).padStart(2, '0')}</div><div className="quest-copy"><div className="quest-title"><h3>{quest.title}</h3><span>{location?.title ?? 'граница'}</span></div><p>{quest.description}</p><div className="quest-progress"><div className="progress-track"><span style={{ width: `${progress}%` }} /></div><small>{quest.progress}/{quest.goal}</small></div></div><div className="quest-reward"><Coins size={13} />+{quest.rewardLmn}<span>LMN</span>{quest.status === 'available' && <button type="button" className="icon-action" onClick={() => onStart(quest)} disabled={pending} aria-label={`Начать ${quest.title}`} data-testid={`button-start-quest-${quest.id}`}><ChevronRight size={16} /></button>}{quest.status === 'completed' && <button type="button" className="button button-small button-gold" onClick={() => onClaim(quest)} disabled={pending} data-testid={`button-claim-quest-${quest.id}`}>забрать</button>}{quest.status === 'in_progress' && <span className="quest-state">идёт</span>}{quest.status === 'locked' && <span className="quest-state">закрыто</span>}{quest.status === 'claimed' && <span className="quest-state done">получено</span>}</div></article>; })}</div></section>;
}

function Reports({ reports }: { reports: GameBattleReport[] }) {
  return <section className="paper-panel reports-panel" data-testid="panel-reports"><div className="section-head"><div><span className="eyebrow"><Medal size={12} /> последние донесения</span><h2>Боевые отчёты</h2></div><span className="panel-count">{reports.length} записей</span></div>{reports.length === 0 ? <div className="empty-inline">Разведчики ещё не прислали донесений.</div> : <div className="report-list">{reports.slice(0, 4).map((report) => <div className="report-row" key={report.id} data-testid={`row-report-${report.id}`}><span className={`report-result result-${report.result}`}>{report.result === 'victory' ? <Check size={14} /> : report.result === 'defeat' ? <X size={14} /> : <Compass size={14} />}</span><div><strong>{report.opponent}</strong><span>{report.battleType === 'scout' ? 'разведка' : 'столкновение'} · {timeAgo(report.createdAt)}</span></div><b>{report.powerDelta > 0 ? `+${report.powerDelta} мощи` : report.reward}</b></div>)}</div>}</section>;
}

export default function GamePage() {
  const tg = useTelegramWebApp();
  const telegramAvailable = isInsideTelegram();
  const initData = tg?.initData ?? '';
  const liveMode = telegramAvailable && Boolean(initData);
  const [gameState, setGameState] = useState<GameState | null>(liveMode ? null : previewState);
  const [hasLoaded, setHasLoaded] = useState(!liveMode);
  const [selectedTileId, setSelectedTileId] = useState('t-32');
  const [notice, setNotice] = useState<Notice | null>(null);
  const [lastSync, setLastSync] = useState(previewState.serverTime);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [realtimeStatus, setRealtimeStatus] = useState<RealtimeStatus>(liveMode ? 'connecting' : 'fallback');
  const getGameState = useGetGameState();
  const startGameQuest = useStartGameQuest();
  const claimGameQuest = useClaimGameQuest();
  const performCommand = usePerformGameCommand();
  const commandRef = useRef(performCommand.mutate);
  commandRef.current = performCommand.mutate;
  const syncRef = useRef(getGameState.mutate);
  syncRef.current = getGameState.mutate;

  const applyState = useCallback((nextState: GameState, successText?: string) => {
    setGameState(nextState);
    setLastSync(nextState.serverTime);
    if (successText) setNotice({ kind: 'success', text: successText });
  }, []);

  const loadState = useCallback((quiet = false) => {
    if (!liveMode) {
      setGameState(previewState);
      setLastSync(previewState.serverTime);
      setHasLoaded(true);
      return;
    }
    if (!quiet) setIsRefreshing(true);
    syncRef.current({ data: { initData } }, {
      onSuccess: (nextState) => { applyState(nextState); setHasLoaded(true); setIsRefreshing(false); },
      onError: () => { setHasLoaded(true); setIsRefreshing(false); setNotice({ kind: 'error', text: 'Не удалось получить свежую летопись. Показываем последнее сохранение.' }); },
    });
  }, [applyState, initData, liveMode]);

  useEffect(() => { loadState(); }, [loadState]);
  useEffect(() => {
    if (!liveMode) return;
    const interval = window.setInterval(() => loadState(true), 45000);
    return () => window.clearInterval(interval);
  }, [loadState, liveMode]);
  useEffect(() => {
    if (!liveMode) {
      setRealtimeStatus('fallback');
      return;
    }

    let stopped = false;
    let retryTimer: number | undefined;
    let retryDelay = 3000;
    let controller: AbortController | undefined;

    const scheduleReconnect = () => {
      if (stopped) return;
      setRealtimeStatus('fallback');
      retryTimer = window.setTimeout(connect, retryDelay);
      retryDelay = Math.min(retryDelay * 2, 30_000);
    };

    const connect = async () => {
      if (stopped) return;
      controller = new AbortController();
      setRealtimeStatus('connecting');
      try {
        const response = await fetch('/api/game/stream', {
          method: 'POST',
          headers: { 'Accept': 'text/event-stream', 'Content-Type': 'application/json' },
          body: JSON.stringify({ initData }),
          signal: controller.signal,
        });
        if (!response.ok || !response.body) throw new Error(`Realtime stream failed: ${response.status}`);

        retryDelay = 3000;
        setRealtimeStatus('live');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (!stopped) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const messages = buffer.split(/\r?\n\r?\n/);
          buffer = messages.pop() ?? '';
          for (const message of messages) {
            const event = message.match(/^event:\s*(.+)$/m)?.[1]?.trim();
            if (event === 'world_changed') loadState(true);
          }
        }
        if (!stopped) scheduleReconnect();
      } catch {
        if (!stopped) scheduleReconnect();
      }
    };

    void connect();
    return () => {
      stopped = true;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      controller?.abort();
    };
  }, [initData, liveMode, loadState]);
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 5000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const selectedTile = useMemo(() => gameState?.map.tiles.find((tile) => tile.id === selectedTileId) ?? gameState?.map.tiles[0], [gameState, selectedTileId]);
  const pending = performCommand.isPending || startGameQuest.isPending || claimGameQuest.isPending;

  const localCommand = useCallback((action: CommandAction, targetId?: string, quantity = 1, name?: string, tag?: string) => {
    setGameState((current) => {
      if (!current) return current;
      const next = structuredClone(current) as GameState;
      if (action === 'collect_resources') {
        next.kingdom.resources.food += 120; next.kingdom.resources.wood += 80; next.kingdom.resources.stone += 45; next.kingdom.resources.iron += 24;
      }
      if (action === 'upgrade_building' && targetId) { const item = next.kingdom.buildings.find((building) => building.id === targetId); if (item) { item.level += 1; next.kingdom.power += 85; } }
      if (action === 'research' && targetId) { const item = next.kingdom.research.find((research) => research.id === targetId); if (item) { item.level += 1; next.kingdom.power += 55; } }
      if (action === 'train_army' && targetId) { next.kingdom.army[targetId as 'infantry' | 'archer' | 'cavalry'] += quantity; next.kingdom.army.totalPower += quantity * 12; next.kingdom.power += quantity * 12; }
      if (action === 'scout' && targetId) { const tile = next.map.tiles.find((item) => item.id === targetId); if (tile) tile.discovered = true; next.reports.unshift({ id: `preview-${Date.now()}`, battleType: 'scout', opponent: selectedTile?.label ?? 'неизвестная точка', result: 'discovered', powerDelta: 0, reward: 'новые сведения на карте', createdAt: new Date().toISOString() }); }
      if (action === 'attack_npc' && targetId) { const tile = next.map.tiles.find((item) => item.id === targetId); if (tile) { next.reports.unshift({ id: `preview-${Date.now()}`, battleType: 'npc', opponent: tile.label, result: 'victory', powerDelta: 120, reward: tile.reward ?? 'слава границы', createdAt: new Date().toISOString() }); next.kingdom.power += 120; } }
      if (action === 'contribute_event' && targetId) { const event = next.events.find((item) => item.id === targetId); if (event) event.progress = Math.min(event.goal, event.progress + quantity); }
      if (action === 'create_alliance') next.alliance = { id: `preview-${Date.now()}`, name: name ?? 'Новый союз', tag: tag ?? 'NEW', role: 'leader', memberCount: 1, description: 'Дом, который только начинает свою летопись.' };
      if (action === 'join_alliance') next.alliance = { id: 'alliance-ash', name: 'Пепельный дозор', tag: 'ASH', role: 'member', memberCount: 19, description: 'Союз домов, которые держат границу, пока короли спорят о гербах.' };
      if (action === 'leave_alliance') next.alliance = null;
      return next;
    });
  }, [selectedTile]);

  const runCommand = useCallback((action: CommandAction, text: string, targetId?: string, quantity?: number, name?: string, tag?: string) => {
    setNotice(null);
    if (!liveMode) { localCommand(action, targetId, quantity, name, tag); setNotice({ kind: 'success', text: `${text}. Изменения сохранены в предпросмотре.` }); return; }
    const data: GameCommandInput = { initData, action, ...(targetId ? { targetId } : {}), ...(quantity ? { quantity } : {}), ...(name ? { name } : {}), ...(tag ? { tag } : {}) };
    commandRef.current({ data }, { onSuccess: (nextState) => applyState(nextState, text), onError: () => setNotice({ kind: 'error', text: 'Команда не выполнена. Проверь связь и повтори действие.' }) });
  }, [applyState, initData, liveMode, localCommand]);

  const startQuest = (quest: GameQuest) => {
    if (!liveMode) { localCommand('collect_resources'); setGameState((current) => current ? { ...current, quests: current.quests.map((item) => item.id === quest.id ? { ...item, progress: item.goal, status: 'completed' } : item) } : current); setNotice({ kind: 'success', text: 'Задание начато. В предпросмотре дозор уже вернулся.' }); return; }
    startGameQuest.mutate({ questId: quest.id, data: { initData } }, { onSuccess: (nextState) => applyState(nextState, 'Задание начато'), onError: () => setNotice({ kind: 'error', text: 'Не удалось начать задание.' }) });
  };
  const claimQuest = (quest: GameQuest) => {
    if (!liveMode) { setGameState((current) => current ? { ...current, player: { ...current.player, gameLmn: current.player.gameLmn + quest.rewardLmn, xp: current.player.xp + 40 }, quests: current.quests.map((item) => item.id === quest.id ? { ...item, status: 'claimed' } : item) } : current); setNotice({ kind: 'success', text: `Награда +${quest.rewardLmn} LMN добавлена в летопись.` }); return; }
    claimGameQuest.mutate({ questId: quest.id, data: { initData } }, { onSuccess: (nextState) => applyState(nextState, 'Награда получена'), onError: () => setNotice({ kind: 'error', text: 'Не удалось забрать награду.' }) });
  };

  if (liveMode && !hasLoaded && !getGameState.isError) return <LoadingState />;
  if (liveMode && getGameState.isError && !gameState) return <ErrorState onRetry={() => loadState()} />;
  if (!gameState) return <ErrorState onRetry={() => loadState()} />;
  const liveEvent = gameState.events.find((event) => event.status === 'live') ?? gameState.events[0];
  const xpPercent = Math.min(100, Math.round((gameState.player.xp / gameState.player.xpToNext) * 100));

  return <main className="game-page">
    <header className="game-topbar">
      <Link className="game-mark" href="/" data-testid="link-game-home"><span><Castle size={19} /></span><div><strong>LUMENA</strong><small>пограничная хроника</small></div></Link>
      <div className="topbar-player" data-testid="text-player-summary"><div className="player-medallion">{gameState.player.displayName.slice(0, 1)}</div><div><strong>{gameState.player.displayName}</strong><span>уровень {gameState.player.level} · {gameState.kingdom.name}</span></div><div className="xp-mini"><i style={{ width: `${xpPercent}%` }} /></div></div>
       <div className="topbar-stats"><span data-testid="text-streak"><Flame size={14} /> {gameState.streak} дней</span><span data-testid="text-game-lmn"><Coins size={14} /> {formatNumber(gameState.player.gameLmn)}</span><span className={`realtime-status realtime-${realtimeStatus}`} data-testid="status-game-realtime"><i className="live-dot" /> {realtimeStatus === 'live' ? 'realtime' : realtimeStatus === 'connecting' ? 'подключение' : 'polling'}</span><button type="button" onClick={() => loadState()} disabled={isRefreshing || pending} aria-label="Обновить состояние" data-testid="button-refresh-game"><RefreshCw size={15} className={isRefreshing ? 'spin' : ''} /></button></div>
    </header>
    {!liveMode && <div className="preview-ribbon" data-testid="banner-preview-mode"><Sparkles size={15} /><span><strong>Режим предпросмотра.</strong> Все приказы работают локально. В Telegram состояние сохраняется через реальный игровой архив.</span><span className="ribbon-badge">OFFLINE CHRONICLE</span></div>}
    {notice && <div className={`game-notice notice-${notice.kind}`} role="status" data-testid={`status-game-${notice.kind}`}><span>{notice.kind === 'success' ? <Check size={15} /> : <AlertTriangle size={15} />}</span>{notice.text}<button type="button" onClick={() => setNotice(null)} aria-label="Закрыть уведомление" data-testid="button-dismiss-notice"><X size={14} /></button></div>}
    <div className="game-shell">
      <aside className="game-rail"><span className="rail-label">командный центр</span><a className="rail-item active" href="#overview" data-testid="link-game-overview"><Castle size={16} /><span>Королевство</span></a><a className="rail-item" href="#map" data-testid="link-game-map"><MapIcon size={16} /><span>Карта мира</span></a><a className="rail-item" href="#city" data-testid="link-game-city"><Landmark size={16} /><span>Город</span></a><a className="rail-item" href="#army" data-testid="link-game-army"><Swords size={16} /><span>Армия</span></a><a className="rail-item" href="#chronicle" data-testid="link-game-chronicle"><ScrollText size={16} /><span>Летопись</span></a><div className="rail-bottom"><span className="online-dot" />{gameState.onlinePlayers} домов онлайн</div></aside>
      <div className="game-content" id="overview">
        <div className="command-heading"><div><span className="eyebrow"><span className="live-dot" /> состояние границы · {gameState.onlinePlayers} домов в сети</span><h1>Доброе утро,<br /><em>{gameState.player.displayName.split(' ')[0]}.</em></h1><p>Туман отступает. Твои приказы ждут у карты.</p></div><div className="server-note"><span>ПОСЛЕДНЯЯ СИНХРОНИЗАЦИЯ</span><strong>{liveMode ? timeAgo(lastSync) : 'предпросмотр'}</strong></div></div>
        <section className="kingdom-banner"><div className="banner-copy"><span className="eyebrow">личное королевство</span><h2>{gameState.kingdom.name}</h2><p>Пятый рубеж · сила {formatNumber(gameState.kingdom.power)}</p><div className="banner-stats"><StatLine label="уровень" value={String(gameState.kingdom.level)} icon={Crown} /><StatLine label="гарнизон" value={formatNumber(gameState.kingdom.army.totalPower)} icon={Shield} /><StatLine label="альянс" value={gameState.alliance ? `[${gameState.alliance.tag}]` : 'нет'} icon={Users} /></div></div><div className="banner-crest"><div className="crest-ring"><Castle size={39} /></div><span>VAL · ROAN</span></div></section>
        <ResourceStrip kingdom={gameState.kingdom} onCollect={() => runCommand('collect_resources', 'Доход собран')} pending={pending} />
         <div className="map-section" id="map"><WorldMap tiles={gameState.map.tiles} selectedId={selectedTile?.id ?? ''} onSelect={(tile) => setSelectedTileId(tile.id)} onScout={() => selectedTile && runCommand('scout', 'Разведка завершена', selectedTile.id)} onAttack={() => selectedTile && runCommand(selectedTile.kind === 'player' ? 'attack_player' : 'attack_npc', 'Приказ отправлен', selectedTile.kind === 'player' ? selectedTile.id : selectedTile.id)} pending={pending} /></div>
        <div className="dual-grid" id="city"><Buildings buildings={gameState.kingdom.buildings} onUpgrade={(building) => runCommand('upgrade_building', `${building.name} улучшена`, building.id)} pending={pending} /><Research research={gameState.kingdom.research} onResearch={(item) => runCommand('research', `${item.name} исследована`, item.id)} pending={pending} /></div>
        <div className="dual-grid" id="army"><Army kingdom={gameState.kingdom} onTrain={(unit) => runCommand('train_army', 'Новые бойцы в строю', unit, 5)} pending={pending} /><EventPanel event={liveEvent} onContribute={() => liveEvent && runCommand('contribute_event', 'Вклад отправлен в событие', liveEvent.id, 50)} pending={pending} /></div>
        <div className="lower-grid" id="chronicle"><AlliancePanel alliance={gameState.alliance} onCreate={(name, tag) => runCommand('create_alliance', 'Союз основан', undefined, undefined, name, tag)} onJoin={() => runCommand('join_alliance', 'Ты вступил в Пепельный дозор')} onLeave={() => runCommand('leave_alliance', 'Ты покинул союз')} pending={pending} /><Reports reports={gameState.reports} /></div>
        <QuestPanel state={gameState} onStart={startQuest} onClaim={claimQuest} pending={pending} />
        <footer className="game-footer"><span>LUMENA / BORDER CHRONICLE</span><span>серверное время: {new Date(gameState.serverTime).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}</span><span><Check size={12} /> архив доступен</span></footer>
      </div>
    </div>
  </main>;
}