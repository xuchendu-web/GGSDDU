import { describe, expect, it } from 'vitest';
import {
  approvedPool,
  assignExperiment,
  captureEvent,
  draw,
  restore,
  type DrawRecord,
  type EventRecord,
  type Repository
} from '../cloudfunctions/draw/core';
import { CARDS } from '../miniprogram/data/cards';
import { buildSharePath } from '../miniprogram/utils/service';

class MemoryRepository implements Repository {
  draws = new Map<string, DrawRecord>();
  events: EventRecord[] = [];
  offlineIds: string[] = [];

  async saveDraw(record: DrawRecord) {
    if (this.draws.has(record.drawId)) throw new Error('drawId must be immutable');
    this.draws.set(record.drawId, structuredClone(record));
  }
  async getDraw(drawId: string) {
    return this.draws.get(drawId) || null;
  }
  async saveEvent(record: EventRecord) {
    this.events.push(record);
  }
  async getOfflineCardIds() {
    return this.offlineIds;
  }
}

describe('reviewed content pool', () => {
  it('contains only approved cards and respects themes', () => {
    const pool = approvedPool([], 'preopen');
    expect(pool).toHaveLength(12);
    expect(pool.every((card) => card.reviewStatus === 'approved' && card.category === 'preopen')).toBe(true);
  });

  it('removes remotely offline content', () => {
    const first = CARDS[0];
    expect(approvedPool([first.id]).some((card) => card.id === first.id)).toBe(false);
  });
});

describe('draw lifecycle', () => {
  it('persists a draw and restores the same card', async () => {
    const repository = new MemoryRepository();
    const created = await draw(repository, { theme: 'close', anonymousId: 'user-a' }, () => 0.25);
    const restored = await restore(repository, created.drawId);
    expect(created.drawId).toMatch(/^d_/);
    expect(restored).toMatchObject({
      drawId: created.drawId,
      card: { id: created.card.id }
    });
  });

  it('does not replace a card that was taken offline', async () => {
    const repository = new MemoryRepository();
    const created = await draw(repository, {}, () => 0);
    repository.offlineIds = [created.card.id];
    await expect(restore(repository, created.drawId)).resolves.toEqual({
      drawId: created.drawId,
      unavailable: true,
      experiment: created.experiment
    });
  });

  it('assigns experiments deterministically', () => {
    expect(assignExperiment('stable-user')).toEqual(assignExperiment('stable-user'));
  });
});

describe('privacy boundaries', () => {
  it('share URL contains only drawId and fixed attribution', () => {
    const path = buildSharePath('d_safe-id');
    expect(path).toBe('/pages/result/result?drawId=d_safe-id&from=share');
    expect(path).not.toMatch(/question|holding|friend|stock/i);
  });

  it('event ingestion drops free text and unknown fields', async () => {
    const repository = new MemoryRepository();
    await captureEvent(repository, {
      name: 'draw_complete',
      anonymousId: 'anon',
      payload: {
        drawId: 'd_1',
        cardId: 'card-001',
        question: '这段自由文本不得入库',
        friends: ['a', 'b'],
        holdings: 'private'
      }
    });
    expect(repository.events[0].payload).toEqual({
      drawId: 'd_1',
      cardId: 'card-001'
    });
  });

  it('rejects unknown event names', async () => {
    await expect(
      captureEvent(new MemoryRepository(), { name: 'upload_question', payload: {} })
    ).rejects.toThrow('INVALID_EVENT');
  });
});
