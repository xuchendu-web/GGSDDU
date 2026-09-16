import { createHash, randomBytes } from 'node:crypto';
import cardsJson from './cards.generated.json';

export type CardCategory =
  | 'preopen'
  | 'close'
  | 'weekend'
  | 'evidence'
  | 'risk'
  | 'emotion'
  | 'discipline'
  | 'information'
  | 'portfolio'
  | 'review'
  | 'uncertainty'
  | 'life';

export interface ReflectionCard {
  id: string;
  title: string;
  shortAnswer: string;
  reflectionQuestion: string;
  boundary: string;
  category: CardCategory;
  version: string;
  reviewStatus: 'approved' | 'offline' | 'draft';
}

const CARDS = cardsJson as ReflectionCard[];

export interface DrawRecord {
  drawId: string;
  cardId: string;
  createdAt: number;
  attribution?: string;
  experiment: Experiment;
}

export interface Experiment {
  interaction: 'tap' | 'hold';
  animationMs: 500 | 1000;
  shareCopy: 'a' | 'b';
}

export interface EventRecord {
  name: AllowedEvent;
  at: number;
  anonymousId: string;
  payload: Record<string, string | number | boolean>;
}

export interface Repository {
  saveDraw(record: DrawRecord): Promise<void>;
  getDraw(drawId: string): Promise<DrawRecord | null>;
  saveEvent(record: EventRecord): Promise<void>;
  getOfflineCardIds(): Promise<string[]>;
}

const EVENT_NAMES = [
  'home_view',
  'draw_start',
  'draw_complete',
  'share_initiated',
  'share_landing_view',
  'shared_user_draw_start',
  'favorite_add',
  'favorite_remove',
  'restore_failed',
  'about_view'
] as const;

type AllowedEvent = (typeof EVENT_NAMES)[number];

const safePayloadKeys = new Set([
  'drawId',
  'cardId',
  'theme',
  'attribution',
  'parentDrawId',
  'interaction',
  'animationMs',
  'shareCopy'
]);

export function approvedPool(offlineIds: readonly string[], theme?: CardCategory): ReflectionCard[] {
  const offline = new Set(offlineIds);
  return CARDS.filter(
    (card) =>
      card.reviewStatus === 'approved' &&
      !offline.has(card.id) &&
      (!theme || card.category === theme)
  );
}

export function assignExperiment(seed: string): Experiment {
  const bucket = createHash('sha256').update(seed).digest()[0];
  return {
    interaction: bucket % 2 === 0 ? 'tap' : 'hold',
    animationMs: bucket % 4 < 2 ? 500 : 1000,
    shareCopy: bucket % 8 < 4 ? 'a' : 'b'
  };
}

function sanitizeText(value: unknown, maxLength: number): string | undefined {
  if (typeof value !== 'string') return undefined;
  const cleaned = value.replace(/[^a-zA-Z0-9_:/.-]/g, '').slice(0, maxLength);
  return cleaned || undefined;
}

export function createDrawId(): string {
  return `d_${Date.now().toString(36)}_${randomBytes(12).toString('base64url')}`;
}

export async function draw(
  repository: Repository,
  input: { theme?: CardCategory; attribution?: unknown; anonymousId?: unknown },
  random: () => number = Math.random
) {
  const offlineIds = await repository.getOfflineCardIds();
  const pool = approvedPool(offlineIds, input.theme);
  if (!pool.length) throw new Error('NO_APPROVED_CONTENT');
  const card = pool[Math.floor(random() * pool.length)];
  const drawId = createDrawId();
  const anonymousId = sanitizeText(input.anonymousId, 64) || drawId;
  const experiment = assignExperiment(anonymousId);
  const record: DrawRecord = {
    drawId,
    cardId: card.id,
    createdAt: Date.now(),
    attribution: sanitizeText(input.attribution, 80),
    experiment
  };
  await repository.saveDraw(record);
  return { drawId, card, experiment };
}

export async function restore(repository: Repository, drawIdInput: unknown) {
  const drawId = sanitizeText(drawIdInput, 80);
  if (!drawId || !drawId.startsWith('d_')) return null;
  const record = await repository.getDraw(drawId);
  if (!record) return null;
  const offlineIds = await repository.getOfflineCardIds();
  const card = approvedPool(offlineIds).find((item) => item.id === record.cardId);
  if (!card) return { drawId, unavailable: true, experiment: record.experiment };
  return { drawId, card, experiment: record.experiment };
}

export async function captureEvent(
  repository: Repository,
  input: { name?: unknown; payload?: unknown; anonymousId?: unknown }
) {
  if (typeof input.name !== 'string' || !EVENT_NAMES.includes(input.name as AllowedEvent)) {
    throw new Error('INVALID_EVENT');
  }
  const rawPayload =
    input.payload && typeof input.payload === 'object'
      ? (input.payload as Record<string, unknown>)
      : {};
  const payload: Record<string, string | number | boolean> = {};
  for (const [key, value] of Object.entries(rawPayload)) {
    if (!safePayloadKeys.has(key)) continue;
    if (typeof value === 'string') payload[key] = value.slice(0, 100);
    if (typeof value === 'number' && Number.isFinite(value)) payload[key] = value;
    if (typeof value === 'boolean') payload[key] = value;
  }
  await repository.saveEvent({
    name: input.name as AllowedEvent,
    at: Date.now(),
    anonymousId: sanitizeText(input.anonymousId, 64) || 'anonymous',
    payload
  });
  return { accepted: true };
}
