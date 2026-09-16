import { CARDS, type CardCategory, type ReflectionCard } from '../data/cards';

export interface DrawResult {
  drawId: string;
  card: ReflectionCard;
  experiment: { interaction: 'tap' | 'hold'; animationMs: 500 | 1000; shareCopy: 'a' | 'b' };
  source: 'cloud' | 'local';
}

const localExperiment = {
  interaction: 'tap' as const,
  animationMs: 500 as const,
  shareCopy: 'a' as const
};

export async function drawCard(theme?: CardCategory, attribution?: string): Promise<DrawResult> {
  if (wx.cloud) {
    try {
      const response = await wx.cloud.callFunction({
        name: 'draw',
        data: { action: 'draw', theme, attribution }
      });
      return { ...response.result, source: 'cloud' };
    } catch {
      // The local reviewed whitelist keeps the core experience available offline.
    }
  }
  const pool = theme ? CARDS.filter((card) => card.category === theme) : CARDS;
  const card = pool[Math.floor(Math.random() * pool.length)];
  return {
    drawId: `local-${Date.now()}-${card.id}`,
    card,
    experiment: localExperiment,
    source: 'local'
  };
}

export async function restoreDraw(drawId: string): Promise<DrawResult | null> {
  if (drawId.startsWith('local-')) {
    const cardId = drawId.split('-').slice(-2).join('-');
    const card = CARDS.find((item) => item.id === cardId);
    return card ? { drawId, card, experiment: localExperiment, source: 'local' } : null;
  }
  if (!wx.cloud) return null;
  try {
    const response = await wx.cloud.callFunction({
      name: 'draw',
      data: { action: 'restore', drawId }
    });
    return response.result ? { ...response.result, source: 'cloud' } : null;
  } catch {
    return null;
  }
}

export function reportEvent(name: string, payload: Record<string, unknown> = {}): void {
  if (!wx.cloud) return;
  void wx.cloud.callFunction({
    name: 'draw',
    data: { action: 'event', name, payload }
  }).catch(() => undefined);
}

export function buildSharePath(drawId: string): string {
  return `/pages/result/result?drawId=${encodeURIComponent(drawId)}&from=share`;
}
