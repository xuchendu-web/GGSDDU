import type { ReflectionCard } from '../../data/cards';
import { buildSharePath, drawCard, reportEvent, restoreDraw } from '../../utils/service';
import { addRecent, isFavorite, toggleFavorite } from '../../utils/storage';

Page({
  data: {
    loading: true,
    card: null as ReflectionCard | null,
    drawId: '',
    source: '',
    shared: false,
    favoriteText: '这页留着',
    shareCopy: 'a'
  },
  async onLoad(options: { drawId?: string; from?: string }) {
    const drawId = decodeURIComponent(options.drawId || '');
    const shared = options.from === 'share';
    const result = drawId ? await restoreDraw(drawId) : await drawCard();
    if (result) {
      addRecent(result.card);
      this.setData({
        loading: false,
        card: result.card,
        drawId: result.drawId,
        source: result.source,
        shared,
        shareCopy: result.experiment.shareCopy,
        favoriteText: isFavorite(result.card.id) ? '已经留着了' : '这页留着'
      });
      reportEvent(shared ? 'share_landing_view' : 'draw_complete', {
        drawId: result.drawId,
        cardId: result.card.id
      });
    } else {
      this.setData({ loading: false, shared });
      reportEvent('restore_failed', { drawId });
    }
  },
  favorite() {
    const card = this.data.card;
    if (!card) return;
    const active = toggleFavorite(card);
    this.setData({ favoriteText: active ? '已经留着了' : '这页留着' });
    reportEvent(active ? 'favorite_add' : 'favorite_remove', { cardId: card.id });
  },
  async drawOwn() {
    reportEvent('shared_user_draw_start', { parentDrawId: this.data.drawId });
    const result = await drawCard(undefined, this.data.drawId);
    wx.redirectTo({ url: `/pages/result/result?drawId=${encodeURIComponent(result.drawId)}` });
  },
  backHome() {
    wx.reLaunch({ url: '/pages/index/index' });
  },
  onShareAppMessage() {
    reportEvent('share_initiated', { drawId: this.data.drawId });
    const title =
      this.data.shareCopy === 'a'
        ? '没别的意思，这页有点像你'
        : '随手翻到这句，你看看';
    return {
      title,
      path: buildSharePath(this.data.drawId)
    };
  }
});
