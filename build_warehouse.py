#!/usr/bin/env python3
"""抓取 sources.json 里的每个源，校验后生成 TVBox 多仓 warehouse.json + 状态 status.json。

两条保护（2026-10-25 加）：
1. 全挂/大幅减少时不覆盖 warehouse.json —— 避免一次抖动把电视端的源清空。
2. 遇到"多仓"源（含 urls 列表）时展开平铺 —— 避免套娃成 {urls:[{url: 另一个多仓}]}。
"""
import json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "okhttp/3.15"
RETRY = 2            # 单源最多尝试次数（防偶发超时误判）
MIN_RATIO = 0.5      # 存活数低于上次的 50% 时视为异常，不覆盖

WAREHOUSE = os.path.join(HERE, "warehouse.json")
STATUS = os.path.join(HERE, "status.json")


def fetch(url):
    last = None
    for i in range(RETRY):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read()
        except Exception as e:
            last = e
            if i + 1 < RETRY:
                time.sleep(1.5 * (i + 1))
    raise last


def parse(body):
    try:
        d = json.loads(body.decode("utf-8-sig"))
    except Exception:
        return None
    return d if isinstance(d, dict) else None


def kind_of(d):
    for k in ("sites", "urls", "lives"):
        v = d.get(k)
        if isinstance(v, list) and v:
            return k
    return None


def prev_count():
    """上次 warehouse.json 里的源数量，用于判断本次是否大幅缩水。"""
    try:
        d = json.load(open(WAREHOUSE, encoding="utf-8"))
        u = d.get("urls")
        return len(u) if isinstance(u, list) else 0
    except Exception:
        return 0


def flatten(name, d):
    """多仓源展开：取出每个子条目的 url，变成独立单仓条目。"""
    out = []
    for it in d.get("urls", []):
        if not isinstance(it, dict):
            continue
        u = it.get("url")
        if not isinstance(u, str) or not u.startswith("http"):
            continue
        sub = it.get("name") or ""
        out.append({"url": u, "name": ("%s/%s" % (name, sub)) if sub else name})
    return out


def main():
    src = json.load(open(os.path.join(HERE, "sources.json"), encoding="utf-8-sig"))
    alive, report = [], []
    for s in src:
        name = s.get("name") or s.get("url")
        url = s.get("url", "")
        if not s.get("enabled", True):
            report.append({"name": name, "url": url, "ok": False, "reason": "disabled"})
            continue
        t0 = time.time()
        try:
            body = fetch(url)
            d = parse(body)
            k = kind_of(d) if d else None
            if not k:
                report.append({"name": name, "url": url, "ok": False, "reason": "not a tvbox config"})
                print("[bad] %s not a tvbox config" % name)
                continue
            if k == "urls":
                subs = flatten(name, d)
                if not subs:
                    report.append({"name": name, "url": url, "ok": False, "reason": "multi-warehouse without valid urls"})
                    print("[bad] %s multi-warehouse empty" % name)
                    continue
                alive.extend(subs)
                cnt = len(subs)
            else:
                alive.append({"url": url, "name": name})
                cnt = len(d[k])
            report.append({"name": name, "url": url, "ok": True, "kind": k, "count": cnt,
                           "ms": int((time.time() - t0) * 1000), "bytes": len(body)})
            print("[ok]  %s %s %d" % (name, k, cnt))
        except Exception as e:
            report.append({"name": name, "url": url, "ok": False, "reason": str(e)[:120]})
            print("[bad] %s %s" % (name, e))

    # 去重（同一 url 只保留第一条）
    seen, uniq = set(), []
    for a in alive:
        if a["url"] in seen:
            continue
        seen.add(a["url"])
        uniq.append(a)
    alive = uniq

    prev = prev_count()
    reason = None
    if not alive:
        reason = "no source alive"
    elif prev and len(alive) < max(1, int(prev * MIN_RATIO)):
        reason = "shrank from %d to %d (<%d%%)" % (prev, len(alive), MIN_RATIO * 100)

    kept = False
    if reason:
        kept = True
        print("[warn] %s — 保留旧 warehouse.json（%d 个源）" % (reason, prev))
    else:
        json.dump({"urls": alive}, open(WAREHOUSE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print("warehouse.json 已更新：%d 个源" % len(alive))

    json.dump({"checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "alive": len(alive), "total": len(src),
               "kept_previous": kept, "previous_count": prev,
               "note": reason or "",
               "sources": report},
              open(STATUS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("%d/%d alive%s" % (len(alive), len(src), "（未覆盖）" if kept else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
