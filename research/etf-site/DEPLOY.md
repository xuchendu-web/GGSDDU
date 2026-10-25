# ETF 分析站 · 部署说明

静态站：`python3 build.py` 生成 `dist/`，nginx 直接托管。依赖：Python3 + pandas + jinja2 + markdown（仅构建机需要，服务器只需 nginx）。

## 公安联网备案
数据码（Michael 提供，2026-10-17）：`37fa37a864125e91c1d3daaeeb0badd6`

页面底部备案链接占位（上线前按实际域名改）：
```html
<a href="https://beian.mps.gov.cn/#/query/webSearch?code=37fa37a864125e91c1d3daaeeb0badd6" rel="noreferrer" target="_blank">公安联网备案</a>
```

## 禁区（与 MIGA 远程隧道共存时）
Michael 2026-10-17：腾讯云上另有远程控制通道，部署 ETF 站**绝对不能影响它**。
- 不改其安全组/防火墙规则、端口、进程、systemd、反向隧道（含 `123.206.194.233` 隧道用途：7000 / 13389 等）
- 站点只用**独立站点目录** + **独立 nginx server 块**
- 只开/确认 **80/443** 给站点；有冲突先停下来问，不要猜

## 需要 Michael 提供
1. 服务器公网 IP、OS 版本（推荐 Ubuntu 22.04/24.04 或 Debian 12）
2. 一个可 SSH 的用户（建议新建 `deploy`，有 sudo 或对 /var/www/etf-site 有写权限）
3. SSH 登录方式：把我们生成的公钥加进该用户 `~/.ssh/authorized_keys`（不需要密码）
4. 域名，以及 DNS：A 记录 `@`（和 `www`）→ 服务器 IP
5. 云安全组放行 22 / 80 / 443
6. 若服务器在中国大陆：域名需已 ICP 备案，否则 80/443 会被拦

## 服务器一次性初始化（Ubuntu）
```bash
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx rsync
sudo mkdir -p /var/www/etf-site && sudo chown deploy:deploy /var/www/etf-site
sudo tee /etc/nginx/sites-available/etf-site <<'NG'
server { listen 80; server_name example.com www.example.com;
  root /var/www/etf-site; index index.html; location / { try_files $uri $uri/ =404; } }
NG
sudo ln -s /etc/nginx/sites-available/etf-site /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d example.com -d www.example.com   # HTTPS，自动续期
```
（把 example.com 换成实际域名）

## 一键部署
```bash
SERVER_HOST=<IP或域名> SERVER_USER=deploy SSH_KEY=~/.ssh/etf_site ./deploy.sh
```
可选 `REMOTE_DIR`（默认 /var/www/etf-site）。定时刷新：在 box 上 cron 每日跑同一命令。

## 隐私
市场分析只取 weekly-tape-review，并过滤含"持仓/账户/成本价/份额/下单"的行；模拟组合只显示权重。新增数据源请改 `sources.py`。

## 已部署（2026-10-17）
- 主机：`123.206.194.233`（OpenCloudOS 9.6 / 宝塔 lhins-ox6egmj0）
- 域名：`etf-abc.cn`（nginx vhost 已配；**DNS A 记录尚未生效**，需在 DNSPod 添加 `@` → `123.206.194.233`，可选 `www`）
- 站点目录：`/www/wwwroot/etf-abc.cn`
- 独立 vhost：`/www/server/panel/vhost/nginx/etf-abc.cn.conf`（及 IP default `etf-abc.cn-ip.conf`）
- SSH：`root` + `~/.ssh/tencent_lighthouse_ed25519`（`etf_site_deploy` 暂未授权）
- 发布：`SERVER_HOST=123.206.194.233 SERVER_USER=root SSH_KEY=~/.ssh/tencent_lighthouse_ed25519 REMOTE_DIR=/www/wwwroot/etf-abc.cn ./deploy.sh`
- 禁区已遵守：未改 iptables/RTUN-ALLOW、未动 rtun-rdp / :7000 / :13389
- HTTPS：未上（无现成证书；等 A 记录后再 certbot/宝塔申请）
