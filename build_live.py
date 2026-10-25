#!/usr/bin/env python3
"""从公开直播源生成「央视 + 卫视」的 TVBox 直播源。

输出：
  live.m3u  —— m3u 格式（支持 #EXTINF group-title）
  live.txt  —— TVBox 纯文本格式（分组,#genre#）

只保留央视 CCTV1-17 / CCTV5+ / CCTV4K 与各省卫视，每个频道最多保留 N 个源（按来源优先级）。
"""
import json, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "okhttp/3.15"
MAX_PER_CHANNEL = 12          # 每个频道最多保留几个源
TIMEOUT = 25

# 来源优先级（越靠前越优先保留）
SOURCES = [
    ("ccsh",      "https://cdn.jsdelivr.net/gh/CCSH/IPTV@main/live.m3u"),
    ("4yt1k",     "https://cdn.jsdelivr.net/gh/4yt1k/m3u-autoupdate@master/output/result.m3u"),
    ("fanmingming","https://cdn.jsdelivr.net/gh/fanmingming/live@main/tv/m3u/itv.m3u"),
    ("yuechan",   "https://cdn.jsdelivr.net/gh/YueChan/Live@main/IPTV.m3u"),
    ("suxuang",   "https://cdn.jsdelivr.net/gh/suxuang/myIPTV@main/back/ipv4_0226.m3u"),
    ("qwerttvv",  "https://cdn.jsdelivr.net/gh/qwerttvv/Beijing-IPTV@master/IPTV-Unicom.m3u"),
    ("ngo5",      "https://cdn.jsdelivr.net/gh/ngo5/IPTV@main/m3u/ipv4.m3u"),
    ("vbskycn",   "https://cdn.jsdelivr.net/gh/vbskycn/iptv@master/tv/iptv4.m3u"),
    ("guovin",    "https://cdn.jsdelivr.net/gh/Guovin/iptv-api@gd/output/result.m3u"),
    ("iptv-org",  "https://cdn.jsdelivr.net/gh/iptv-org/iptv@master/streams/cn.m3u"),
]

# 卫视白名单（顺序即输出顺序）
SATELLITE = [
    "湖南卫视", "浙江卫视", "江苏卫视", "东方卫视", "北京卫视", "安徽卫视",
    "山东卫视", "广东卫视", "深圳卫视", "天津卫视", "四川卫视", "重庆卫视",
    "湖北卫视", "河南卫视", "河北卫视", "辽宁卫视", "黑龙江卫视", "吉林卫视",
    "江西卫视", "东南卫视", "贵州卫视", "云南卫视", "广西卫视", "甘肃卫视",
    "宁夏卫视", "青海卫视", "新疆卫视", "内蒙古卫视", "西藏卫视", "海南卫视",
    "山西卫视", "陕西卫视", "三沙卫视", "厦门卫视", "延边卫视", "兵团卫视",
]

CCTV_ORDER = ["CCTV%d" % i for i in range(1, 18)] + ["CCTV5+", "CCTV4K"]


def fetch(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read().decode("utf-8-sig", "replace")
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise last


def parse_m3u(text):
    """返回 [(name, url, group)]"""
    out, name, group = [], None, ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            group = ""
            m = re.search(r'group-title="([^"]*)"', line)
            if m:
                group = m.group(1)
            name = line.split(",")[-1].strip()
        elif line.startswith("#"):
            continue
        elif name:
            out.append((name, line, group))
            name = None
    return out


def canon(name):
    """把频道名归一化为 CCTVx / 卫视名；不是目标频道返回 None。"""
    n = name.replace(" ", "").replace("－", "-").replace("—", "-")
    m = re.search(r'(?i)cctv[-\s_]?(\d{1,2})(\+)?', n)
    if m:
        num, plus = m.group(1), m.group(2)
        key = "CCTV%s%s" % (int(num), "+" if plus else "")
        return key if key in CCTV_ORDER else None
    if re.search(r'(?i)cctv[-\s_]?4k', n):
        return "CCTV4K"
    for s in SATELLITE:
        if s in n:
            return s
    return None


def build_pool():
    """抓取所有来源，返回 {频道: [urls]} 与来源统计。"""
    pool = {}
    stats = []
    for src_name, url in SOURCES:
        try:
            text = fetch(url)
        except Exception as e:
            stats.append({"source": src_name, "ok": False, "reason": str(e)[:100]})
            print("[bad] %s %s" % (src_name, e))
            continue
        items = parse_m3u(text)
        got = 0
        for name, u, _g in items:
            key = canon(name)
            if not key:
                continue
            lst = pool.setdefault(key, [])
            if u in lst:
                continue
            if any(u in x for x in lst):     # 同一地址被多个源重复登记
                continue
            if len(lst) < MAX_PER_CHANNEL:
                lst.append(u)
                got += 1
        stats.append({"source": src_name, "ok": True, "parsed": len(items), "kept": got})
        print("[ok]  %-10s 解析 %d 条，新增 %d 个可用源" % (src_name, len(items), got))

    pool = apply_checked(pool)
    return pool, stats


def apply_checked(pool):
    """按本机实测结果排序：能播的在前，确认挂掉的在后。"""
    path = os.path.join(HERE, "live_checked.json")
    if not os.path.exists(path):
        return pool
    try:
        chk = json.load(open(path, encoding="utf-8"))
    except Exception:
        return pool

    def rank(u):
        r = chk.get(u)
        if not r:
            return 2                      # 没测过的居中
        return 1 if r.get("ok") else 3    # 可用在前，挂掉在后

    def kbs(u):
        r = chk.get(u) or {}
        return r.get("kbs", 0)

    for k, urls in pool.items():
        urls.sort(key=lambda u: (rank(u), -kbs(u), u))
        # 有实测可用线路时，把确认挂掉的剔除；全都没验证时保留原样
        good = [u for u in urls if (chk.get(u) or {}).get("ok")]
        if good:
            urls[:] = good + [u for u in urls if u not in good and u not in chk]
    return pool


def main():
    pool, stats = build_pool()
    cctv = [c for c in CCTV_ORDER if pool.get(c)]
    sat = [s for s in SATELLITE if pool.get(s)]

    # live.m3u
    lines = ['#EXTM3U']
    for grp, chans in (("央视", cctv), ("卫视", sat)):
        for ch in chans:
            for i, u in enumerate(pool[ch]):
                title = ch if i == 0 else "%s-%d" % (ch, i + 1)
                lines.append('#EXTINF:-1 group-title="%s",%s' % (grp, title))
                lines.append(u)
    m3u = os.path.join(HERE, "live.m3u")
    open(m3u, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")

    # live.txt（TVBox 纯文本）
    txt = []
    for grp, chans in (("央视", cctv), ("卫视", sat)):
        txt.append("%s,#genre#" % grp)
        for ch in chans:
            for i, u in enumerate(pool[ch]):
                title = ch if i == 0 else "%s-%d" % (ch, i + 1)
                txt.append("%s,%s" % (title, u))
    live_txt = os.path.join(HERE, "live.txt")
    open(live_txt, "w", encoding="utf-8", newline="\n").write("\n".join(txt) + "\n")

    meta = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cctv": {c: len(pool[c]) for c in cctv},
        "satellite": {s: len(pool[s]) for s in sat},
        "cctv_channels": len(cctv),
        "satellite_channels": len(sat),
        "sources": stats,
    }
    json.dump(meta, open(os.path.join(HERE, "live_status.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("央视 %d 个频道，卫视 %d 个频道，共 %d 条线路" %
          (len(cctv), len(sat), sum(len(pool[c]) for c in cctv + sat)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
