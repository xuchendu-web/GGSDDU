import { reportEvent } from '../../utils/service';

Page({
  onLoad() {
    reportEvent('about_view');
  }
});
