#!/usr/bin/env python3
"""把「多仓点播源」和「央视/卫视直播」合成一个单仓配置 tvbox.json。

一个地址搞定：点播 + 直播。

关键处理：
- 站点的 api 常是短类名（csp_XXX），依赖各自源的全局 spider jar。
  合并时给这类站点补 `jar` 字段（= 该源的 spider 地址），避免串 jar 后打不开。
- 直播频道用 `urls` 数组承载多条线路，播放器可自行切换。
- 站点为空时保留旧文件，不覆盖。
"""
import json, os, sys, time, urllib.request, urllib.parse
import build_live as BL

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "okhttp/3.15"
OUT = os.path.join(HERE, "tvbox.json")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8-sig", "replace")


def abs_url(base, u):
    return urllib.parse.urljoin(base, u) if u else u


def collect():
    srcs = json.load(open(os.path.join(HERE, "sources.json"), encoding="utf-8-sig"))
    sites, parses, seen_names, seen_parse, stats = [], [], set(), set(), []
    for s in srcs:
        if not s.get("enabled", True):
            continue
        name, url = s.get("name"), s.get("url")
        try:
            d = json.loads(fetch(url))
        except Exception as e:
            stats.append({"name": name, "ok": False, "reason": str(e)[:100]})
            print("[bad] %s %s" % (name, e))
            continue

        jar = d.get("spider") or ""
        if jar:
            jar = abs_url(url, jar)
        added = 0
        for it in d.get("sites") or []:
            if not isinstance(it, dict):
                continue
            nm = it.get("name")
            if not nm or nm in seen_names:
                continue
            site = dict(it)
            api = site.get("api") or ""
            if api and not api.startswith("http"):
                # 短类名 -> 必须绑定来源自己的 jar
                if jar:
                    site["jar"] = jar
                else:
                    continue
            seen_names.add(nm)
            sites.append(site)
            added += 1

        p_added = 0
        for p in d.get("parses") or []:
            if not isinstance(p, dict):
                continue
            pu = p.get("url")
            if not pu or pu in seen_parse:
                continue
            seen_parse.add(pu)
            parses.append(p)
            p_added += 1

        stats.append({"name": name, "ok": True, "sites": added, "parses": p_added})
        print("[ok]  %-55s 站点 +%d  解析 +%d" % (url[:53], added, p_added))
    return sites, parses, stats


def build_lives(pool):
    lives = []
    for group, keys in (("央视", [c for c in BL.CCTV_ORDER if pool.get(c)]),
                        ("卫视", [s for s in BL.SATELLITE if pool.get(s)])):
        if not keys:
            continue
        chans = [{"name": k, "urls": pool[k][:BL.MAX_PER_CHANNEL]} for k in keys]
        lives.append({"group": group, "channels": chans})
    return lives


def main():
    sites, parses, stats = collect()
    pool, live_stats = BL.build_pool()
    lives = build_lives(pool)

    if not sites:
        print("[warn] 没有抓到任何站点，保留旧 tvbox.json")
        return 1

    # 直播抓取失败（网络抖动）时，保留上一次的 lives，避免把直播清空
    if not lives:
        try:
            old = json.load(open(OUT, encoding="utf-8"))
            if old.get("lives"):
                lives = old["lives"]
                print("[warn] lives 抓取失败，沿用上一次的 %d 组" % len(lives))
        except Exception:
            pass

    cfg = {"sites": sites}
    if parses:
        cfg["parses"] = parses
    if lives:
        cfg["lives"] = lives

    json.dump(cfg, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    meta = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sites": len(sites),
        "parses": len(parses),
        "live_groups": [{"group": g["group"], "channels": len(g["channels"])} for g in lives],
        "sources": stats,
        "live_sources": live_stats,
    }
    json.dump(meta, open(os.path.join(HERE, "tvbox_status.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("tvbox.json: %d 个站点 / %d 个解析 / %d 个直播频道" %
          (len(sites), len(parses), sum(len(g["channels"]) for g in lives)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
