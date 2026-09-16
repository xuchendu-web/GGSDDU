App({
  globalData: {
    launchAt: Date.now()
  },
  onLaunch() {
    if (wx.cloud) {
      wx.cloud.init({ traceUser: true });
    }
  }
});
