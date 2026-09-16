import type { ReflectionCard } from '../../data/cards';
import { getFavorites, getRecent } from '../../utils/storage';

Page({
  data: {
    tab: 'favorites' as 'favorites' | 'recent',
    items: [] as ReflectionCard[]
  },
  onShow() {
    this.refresh();
  },
  refresh() {
    this.setData({
      items: this.data.tab === 'favorites' ? getFavorites() : getRecent()
    });
  },
  switchTab(event: { currentTarget: { dataset: { tab: 'favorites' | 'recent' } } }) {
    this.setData({ tab: event.currentTarget.dataset.tab });
    this.refresh();
  },
  openCard(event: { currentTarget: { dataset: { id: string } } }) {
    const card = this.data.items.find((item: ReflectionCard) => item.id === event.currentTarget.dataset.id);
    if (!card) return;
    wx.navigateTo({ url: `/pages/result/result?drawId=local-0-${card.id}` });
  }
});
