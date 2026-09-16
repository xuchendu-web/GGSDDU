import type { ReflectionCard } from '../data/cards';

const FAVORITES_KEY = 'reflection-card-favorites-v1';
const RECENT_KEY = 'reflection-card-recent-v1';
const MAX_RECENT = 20;

export function getFavorites(): ReflectionCard[] {
  return wx.getStorageSync(FAVORITES_KEY) || [];
}

export function isFavorite(cardId: string): boolean {
  return getFavorites().some((card) => card.id === cardId);
}

export function toggleFavorite(card: ReflectionCard): boolean {
  const current = getFavorites();
  const exists = current.some((item) => item.id === card.id);
  wx.setStorageSync(
    FAVORITES_KEY,
    exists ? current.filter((item) => item.id !== card.id) : [card, ...current]
  );
  return !exists;
}

export function addRecent(card: ReflectionCard): void {
  const current: ReflectionCard[] = wx.getStorageSync(RECENT_KEY) || [];
  wx.setStorageSync(
    RECENT_KEY,
    [card, ...current.filter((item) => item.id !== card.id)].slice(0, MAX_RECENT)
  );
}

export function getRecent(): ReflectionCard[] {
  return wx.getStorageSync(RECENT_KEY) || [];
}
