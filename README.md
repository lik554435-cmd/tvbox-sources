# tvbox-sources

自动维护的 TVBox / 影视仓多仓接口。GitHub Actions 每 6 小时检查一次 `sources.json` 里的每个源，
能用的写进 `warehouse.json`，挂掉的自动剔除。电视上只需要填一个固定地址。

## 电视上填哪个地址

**推荐：一个地址搞定（点播 + 直播）**

```
https://cdn.jsdelivr.net/gh/lik554435-cmd/tvbox-sources@main/tvbox.json
https://raw.githubusercontent.com/lik554435-cmd/tvbox-sources/main/tvbox.json
```

这个 `tvbox.json` 是**单仓配置**：297 个点播站点 + 34 个解析 + 54 个直播频道（央视 18 / 卫视 36）全在一个文件里，
填一次就行。

填法：宝盒TV / TVBox → 设置 → 点播 → 粘贴地址 → Done → 确定。
（直播会自动带出来，不用再单独填直播源）

正常跑起来大概是这样：
- `tvbox.json` 装完，直接能看
- 如果某个站点打不开（跨 spider 兼容性问题），用下面的「多仓 + 独立直播」方案兜底
- 如果播放器只认多仓，用 `warehouse.json`；直播单独填 `live.txt`

**方案二：多仓点播 + 独立直播（老办法）**

```
https://cdn.jsdelivr.net/gh/lik554435-cmd/tvbox-sources@main/warehouse.json
```
推荐 jsDelivr（国内可直连）。填法：宝盒TV / TVBox → 设置 → 点播 → 粘贴地址 → Done → 确定。
直播源再单独填下面「直播源」里的 `live.txt`。

## 直播源（央视 + 卫视）

同一个仓库还自动生成直播源，覆盖 **央视 CCTV1–17 + CCTV5+** 和 **36 个省级卫视**，
每个频道给 3–4 条备用线路（名字后带 `-2` `-3` 的是备用）。

```
https://cdn.jsdelivr.net/gh/lik554435-cmd/tvbox-sources@main/live.txt
https://raw.githubusercontent.com/lik554435-cmd/tvbox-sources/main/live.txt
```

m3u 格式（部分播放器用这个）：

```
https://cdn.jsdelivr.net/gh/lik554435-cmd/tvbox-sources@main/live.m3u
```

填法：TVBox → 设置 → 直播 → 直播源地址 → 粘贴 `live.txt` 的地址 → 确定 → 回到首页选「直播」。

想调顺序或频道范围，改 `build_live.py` 里的 `MAX_PER_CHANNEL`（每频道保留几条）和 `SATELLITE`（卫视白名单）。

## 文件

| 文件 | 作用 |
|---|---|
| `sources.json` | 候选源清单，改这个增删源 |
| `build_warehouse.py` | 抓取 + 校验 + 生成多仓 |
| `warehouse.json` | 输出，自动生成，别手改 |
| `status.json` | 输出，每个源的存活/站点数/耗时 |
| `build_live.py` | 生成央视/卫视直播（txt + m3u） |
| `live.txt` / `live.m3u` | 输出，独立直播源 |
| `build_all.py` | 把点播站点 + 直播合成单仓 `tvbox.json` |
| `tvbox.json` | 输出，**一个地址搞定全部** |
| `tvbox_status.json` | 输出，单仓生成状态 |
| `.github/workflows/update.yml` | 每 6 小时定时跑 |

## 增删源

编辑 `sources.json` 加一条：

```json
{ "name": "某源", "url": "https://example.com/api.json", "enabled": true }
```

停用把 `enabled` 改 `false`。改完提交即可，Actions 会自动重跑，
也可以在 Actions → update warehouse → Run workflow 手动触发。

## 校验逻辑

脚本用 `okhttp/3.15` 作为 UA —— 很多源对浏览器返回 HTML、对 App 才返回 JSON，
用浏览器 UA 会误判为失效。判定标准：HTTP 200、能解析成 JSON、且含非空的
`sites` / `urls` / `lives`。

## 注意

这些源都是个人免费维护，随时可能失效。本仓库的价值是**地址固定**，
失效的自动掉，你不用满网找新地址。
