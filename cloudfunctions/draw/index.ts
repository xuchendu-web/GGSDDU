import { captureEvent, draw, restore, type Repository } from './core';

declare const require: (name: string) => any;
const cloud = require('wx-server-sdk');
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });
const db = cloud.database();

const repository: Repository = {
  async saveDraw(record) {
    await db.collection('draws').add({ data: record });
  },
  async getDraw(drawId) {
    const result = await db.collection('draws').where({ drawId }).limit(1).get();
    return result.data[0] || null;
  },
  async saveEvent(record) {
    await db.collection('events').add({ data: record });
  },
  async getOfflineCardIds() {
    try {
      const result = await db.collection('content_config').doc('active').get();
      return Array.isArray(result.data.offlineCardIds) ? result.data.offlineCardIds : [];
    } catch {
      return [];
    }
  }
};

export async function main(event: Record<string, any>, context: Record<string, any>) {
  const wxContext = cloud.getWXContext();
  const anonymousId = wxContext.OPENID || context.requestId || 'anonymous';
  if (event.action === 'draw') {
    return draw(repository, {
      theme: event.theme,
      attribution: event.attribution,
      anonymousId
    });
  }
  if (event.action === 'restore') {
    return restore(repository, event.drawId);
  }
  if (event.action === 'event') {
    return captureEvent(repository, {
      name: event.name,
      payload: event.payload,
      anonymousId
    });
  }
  throw new Error('INVALID_ACTION');
}
