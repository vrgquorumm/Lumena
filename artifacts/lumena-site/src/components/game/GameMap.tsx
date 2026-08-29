import { Cat, Check, Compass, Lock, MapPin, Store, Waves } from 'lucide-react';
import type { GameLocation } from '@workspace/api-client-react';

interface GameMapProps {
  locations: GameLocation[];
  selectedLocationId: string | null;
  onSelectLocation: (location: GameLocation) => void;
}

const locationIcons = [Cat, Store, Waves, Compass];

export function GameMap({ locations, selectedLocationId, onSelectLocation }: GameMapProps) {
  return (
    <section className="game-map-section" aria-labelledby="town-heading">
      <div className="section-kicker"><span className="kicker-dot" /> карта района 01</div>
      <div className="game-section-heading">
        <div>
          <h1 id="town-heading">Город просыпается</h1>
          <p>Выбери место, где сегодня появится что-то новое.</p>
        </div>
        <div className="map-compass" aria-hidden="true"><Compass size={18} /><span>север</span></div>
      </div>

      <div className="town-map" data-testid="map-town">
        <div className="map-sun" />
        <div className="map-cloud cloud-one" />
        <div className="map-cloud cloud-two" />
        <div className="map-hill hill-back" />
        <div className="map-hill hill-front" />
        <div className="map-road road-main" />
        <div className="map-road road-cross" />
        <div className="map-water" />
        <div className="map-pier" />
        <div className="map-town-name">Лумка<br /><em>cozy district</em></div>
        <div className="map-buildings" aria-hidden="true">
          <i className="building building-a" /><i className="building building-b" /><i className="building building-c" />
          <i className="tree tree-a" /><i className="tree tree-b" /><i className="tree tree-c" />
        </div>

        {locations.map((location, index) => {
          const Icon = locationIcons[index % locationIcons.length];
          const isSelected = selectedLocationId === location.id;
          const isLocked = location.state === 'locked';
          return (
            <button
              key={location.id}
              type="button"
              className={`map-location-pin pin-${index + 1} ${isSelected ? 'is-selected' : ''} ${isLocked ? 'is-locked' : ''}`}
              onClick={() => onSelectLocation(location)}
              disabled={isLocked}
              style={{ borderColor: `${location.accent || '#f47b53'}99` }}
              aria-label={`${location.title}, ${isLocked ? 'закрыто' : 'открыть'}`}
              data-testid={`button-location-${location.id}`}
            >
              <span className="location-pin-icon" style={{ background: location.accent || '#f47b53' }}>
                {isLocked ? <Lock size={15} /> : isSelected ? <Check size={16} /> : <Icon size={17} />}
              </span>
              <span className="location-pin-label">{location.title}</span>
              {location.state === 'discovered' && <span className="location-discovered"><MapPin size={10} /></span>}
            </button>
          );
        })}
      </div>

      <div className="location-strip" data-testid="list-locations">
        {locations.map((location) => (
          <button
            key={location.id}
            type="button"
            onClick={() => onSelectLocation(location)}
            disabled={location.state === 'locked'}
            className={`location-strip-item ${selectedLocationId === location.id ? 'is-active' : ''}`}
            data-testid={`button-location-strip-${location.id}`}
          >
            <span className="location-strip-swatch" style={{ background: location.accent || '#f47b53' }} />
            <span>{location.title}</span>
            {location.state === 'locked' ? <Lock size={12} /> : <MapPin size={12} />}
          </button>
        ))}
      </div>
    </section>
  );
}