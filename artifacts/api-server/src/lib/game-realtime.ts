export type GameWorldChange = {
  type: "world_changed";
  serverTime: string;
};

type Subscriber = (change: GameWorldChange) => void;

const subscribers = new Set<Subscriber>();

export function subscribeToGameWorld(subscriber: Subscriber): () => void {
  subscribers.add(subscriber);
  return () => subscribers.delete(subscriber);
}

export function publishGameWorldChange(): void {
  const change: GameWorldChange = {
    type: "world_changed",
    serverTime: new Date().toISOString(),
  };

  for (const subscriber of subscribers) {
    try {
      subscriber(change);
    } catch {
      subscribers.delete(subscriber);
    }
  }
}