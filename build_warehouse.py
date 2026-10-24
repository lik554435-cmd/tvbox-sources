#!/usr/bin/env python3
import json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "okhttp/3.15"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()

def kind(body):
    try:
        d = json.loads(body.decode("utf-8-sig"))
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    for k in ("sites", "urls", "lives"):
        v = d.get(k)
        if isinstance(v, list) and v:
            return k
    return None

def main():
    src = json.load(open(os.path.join(HERE, "sources.json"), encoding="utf-8"))
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
            k = kind(body)
            if k:
                alive.append({"url": url, "name": name})
                report.append({"name": name, "url": url, "ok": True, "kind": k,
                               "count": len(json.loads(body.decode("utf-8-sig"))[k]),
                               "ms": int((time.time() - t0) * 1000), "bytes": len(body)})
                print("[ok]  %s %s" % (name, k))
            else:
                report.append({"name": name, "url": url, "ok": False, "reason": "not a tvbox config"})
                print("[bad] %s" % name)
        except Exception as e:
            report.append({"name": name, "url": url, "ok": False, "reason": str(e)[:120]})
            print("[bad] %s %s" % (name, e))

    json.dump({"urls": alive}, open(os.path.join(HERE, "warehouse.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump({"checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "alive": len(alive), "total": len(src), "sources": report},
              open(os.path.join(HERE, "status.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("%d/%d alive" % (len(alive), len(src)))
    return 0

if __name__ == "__main__":
    sys.exit(main())
