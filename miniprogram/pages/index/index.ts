import type { CardCategory } from '../../data/cards';
import { drawCard, reportEvent } from '../../utils/service';

Page({
  data: {
    loading: false,
    opening: false
  },
  onLoad(options: Record<string, string>) {
    reportEvent('home_view', { attribution: options.from || 'direct' });
  },
  async draw(event: { currentTarget?: { dataset?: { theme?: CardCategory } } }) {
    if (this.data.loading) return;
    const theme = event.currentTarget?.dataset?.theme;
    this.setData({ loading: true, opening: true });
    reportEvent('draw_start', { theme: theme || 'all' });
    const result = await drawCard(theme);
    setTimeout(() => {
      wx.navigateTo({
        url: `/pages/result/result?drawId=${encodeURIComponent(result.drawId)}`
      });
      this.setData({ loading: false, opening: false });
    }, result.experiment.animationMs);
  },
  goLibrary() {
    wx.navigateTo({ url: '/pages/library/library' });
  },
  goAbout() {
    wx.navigateTo({ url: '/pages/about/about' });
  }
});
