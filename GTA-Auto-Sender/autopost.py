r"""Folder -> Zernio. A video in queue/<channel>/ready/ is uploaded to that channel's YouTube + Instagram.

  python autopost.py            post / schedule everything waiting in every ready/ folder
  python autopost.py --dry      show the plan, send nothing
  python autopost.py channel1   only one channel

Next to  <name>.mp4  put  <name>.json  (clip_feeder.py writes it for you):
  {"title": "...", "youtube_description": "...", "instagram_caption": "...", "hashtags": ["#a"],
   "when": "now" | "2026-11-19T21:30:00+05:30", "platforms": ["youtube", "instagram"], "hold": false}
  "when" missing = the next free slot from "post_times" (default 12:00 and 00:00 local).
  "hold": true = leave it alone.  No json = title from the file name.

A video moves to scheduled/ only when every platform accepted it. If one platform fails, the ids that worked
are saved in the json and only the missing platform is retried next run (no double posts).
Keys come from .env (name in channels.json). A key is never printed. Log: queue/autopost.log
"""
import argparse, datetime as dt, os, sys, time, uuid
import requests

from common import API, Q, load_config, load_env, make_logger, read_json, tzinfo, write_json

PLATS = ("youtube", "instagram")


def taken_slots(chdir, headers, accounts, tz):
    """Times already used: local scheduled/ metas + whatever Zernio still has scheduled on THIS channel's accounts."""
    used = set()
    sd = os.path.join(chdir, "scheduled")
    if os.path.isdir(sd):
        for fn in os.listdir(sd):
            if fn.endswith(".json"):
                try:
                    t = read_json(os.path.join(sd, fn)).get("post_at")
                    if t:
                        used.add(dt.datetime.fromisoformat(t).astimezone(tz).replace(second=0, microsecond=0))
                except Exception:
                    pass
    for H in headers:
        try:
            r = requests.get(f"{API}/posts", headers=H, params={"status": "scheduled", "limit": 100}, timeout=30)
            for p in r.json().get("posts", []):
                ids = set()
                for pl in p.get("platforms", []):
                    a = pl.get("accountId")
                    ids.add(a.get("_id") if isinstance(a, dict) else a)
                if ids & accounts and p.get("scheduledFor"):
                    used.add(dt.datetime.fromisoformat(p["scheduledFor"].replace("Z", "+00:00")).astimezone(tz).replace(second=0, microsecond=0))
        except Exception:
            pass
    return used


def next_slot(times, used, tz):
    now = dt.datetime.now(tz); d = now.date()
    hm = sorted(tuple(int(x) for x in t.split(":")) for t in times)
    while True:
        for h, m in hm:
            t = dt.datetime(d.year, d.month, d.day, h, m, tzinfo=tz)
            if t > now + dt.timedelta(minutes=20) and t not in used:
                return t
        d += dt.timedelta(days=1)


def default_meta(name, cfg):
    title = name.replace("_", " ").replace("-", " ").strip().capitalize()
    tags = cfg.get("feeder", {}).get("hashtags", [])
    return {"title": title, "youtube_description": f"{title}\n\n{' '.join(tags)}",
            "instagram_caption": f"{title}\n\n{' '.join(tags)}", "hashtags": tags}


def post_one(plat, acc, H, vp, name, m, ch, when, tzname):
    r = requests.post(f"{API}/media/presign", headers=H, json={"filename": name + ".mp4", "contentType": "video/mp4"}, timeout=60)
    r.raise_for_status(); j = r.json()
    with open(vp, "rb") as f:
        requests.put(j["uploadUrl"], data=f, headers={"Content-Type": "video/mp4"}, timeout=900).raise_for_status()
    body = {"platforms": [{"platform": plat, "accountId": acc}], "mediaItems": [{"type": "video", "url": j["publicUrl"]}],
            "timezone": tzname}
    if when == "now":
        body["publishNow"] = True
    else:
        body["scheduledFor"] = when.isoformat()
    if plat == "youtube":
        body["content"] = m.get("youtube_description") or m["title"]
        body["tags"] = [x.strip("#") for x in m.get("hashtags", [])]
        body["platforms"][0]["platformSpecificData"] = {"title": m["title"][:100], "visibility": "public",
                                                        "categoryId": ch.get("youtube_category", "20"), "madeForKids": False}
    else:
        body["content"] = m.get("instagram_caption") or m["title"]
    r = requests.post(f"{API}/posts", headers={**H, "Idempotency-Key": str(uuid.uuid4())}, json=body, timeout=300)
    try:
        jj = r.json()
    except Exception:
        jj = {"raw": r.text[:300]}
    pid = (jj.get("post") or {}).get("_id")
    return pid, (None if pid else str(jj)[:300])


def runway(cfg, tz, log):
    """Write queue/RUNWAY.md: per channel, the last scheduled time and how many days of posts are left. Under 2 days = LOW."""
    now = dt.datetime.now(tz); rows = []
    for chan in cfg["channels"]:
        sd = os.path.join(Q, chan, "scheduled"); last = None; n = 0
        if os.path.isdir(sd):
            for fn in os.listdir(sd):
                if fn.endswith(".json"):
                    try:
                        t = dt.datetime.fromisoformat(read_json(os.path.join(sd, fn))["post_at"])
                    except Exception:
                        continue
                    n += t > now
                    last = t if last is None or t > last else last
        rd = os.path.join(Q, chan, "ready")
        waiting = len([f for f in os.listdir(rd) if f.endswith(".mp4")]) if os.path.isdir(rd) else 0
        days = max(0.0, (last - now).total_seconds() / 86400) if last else 0.0
        rows.append((days, chan, n, waiting, last))
    rows.sort()
    out = ["# Runway (written by autopost.py)", f"Updated {now:%d %b %H:%M}.", "",
           "| channel | days left | upcoming | in ready/ | last slot |", "|---|---|---|---|---|"]
    for days, chan, n, waiting, last in rows:
        if last:
            out.append(f"| {chan}{' **LOW**' if days < 2 else ''} | {days:.1f} | {n} | {waiting} | {last.astimezone(tz):%a %d %b %H:%M} |")
        else:
            out.append(f"| {chan} **EMPTY** | 0 | 0 | {waiting} | never |")
    open(os.path.join(Q, "RUNWAY.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    low = [c for d, c, *_ in rows if d < 2]
    if low:
        log("RUNWAY LOW (<2 days of posts): " + ", ".join(low))


def run(a, cfg, tz, log):
    tzname = cfg.get("timezone_name", "UTC")
    try:
        runway(cfg, tz, log)
    except Exception as e:
        log(f"runway report failed: {e}")
    E = load_env(); bad = 0
    for chan, ch in cfg["channels"].items():
        if a.channel and chan != a.channel:
            continue
        chdir = os.path.join(Q, chan); rdy = os.path.join(chdir, "ready")
        if not os.path.isdir(rdy):
            continue
        vids = sorted(f[:-4] for f in os.listdir(rdy) if f.lower().endswith(".mp4"))
        vids = [n for n in vids if time.time() - os.path.getmtime(os.path.join(rdy, n + ".mp4")) > 90]   # still being copied
        if not vids:
            continue
        plats = [(p, ch[p + "_account_id"], {"Authorization": "Bearer " + E[ch["key_env"]]})
                 for p in PLATS
                 if ch.get(p + "_account_id") and not ch[p + "_account_id"].startswith("PASTE") and ch.get("key_env") in E]
        if not plats:
            log(f"{chan}: {len(vids)} video(s) waiting but no account/key is set up for it. Skipped."); continue
        used = taken_slots(chdir, [H for _, _, H in plats], {acc for _, acc, _ in plats}, tz)
        times = ch.get("post_times") or cfg.get("post_times") or ["12:00", "00:00"]
        os.makedirs(os.path.join(chdir, "scheduled"), exist_ok=True)
        for name in vids:
            mp = os.path.join(rdy, name + ".json"); vp = os.path.join(rdy, name + ".mp4")
            m = read_json(mp) if os.path.exists(mp) else default_meta(name, cfg)
            if m.get("hold"):
                continue
            w = m.get("when")
            if w == "now":
                when = "now"
            elif w:
                when = dt.datetime.fromisoformat(w)
                if when < dt.datetime.now(tz) + dt.timedelta(minutes=3):   # slot already passed (retry, late run): post now
                    when = "now"
            elif m.get("post_at") and m.get("posted"):                     # half done earlier: keep the same time
                when = dt.datetime.fromisoformat(m["post_at"])
            else:
                when = next_slot(times, used, tz)
            if when != "now":
                used.add(when.astimezone(tz).replace(second=0, microsecond=0))
            label = "NOW" if when == "now" else when.astimezone(tz).strftime("%a %d %b %H:%M")
            done = dict(m.get("posted") or {})
            only = m.get("platforms")                                      # e.g. ["youtube"]: Instagram has a ~50/day API cap
            target = [x for x in plats if not only or x[0] in only]
            todo = [x for x in target if x[0] not in done]
            log(f"{chan}/{name}: {label} -> {[p for p, _, _ in todo]} title={m['title']!r}{' (dry)' if a.dry else ''}")
            if a.dry:
                continue
            for plat, acc, H in todo:
                try:
                    pid, err = post_one(plat, acc, H, vp, name, m, ch, when, tzname)
                except Exception as e:
                    pid, err = None, f"{type(e).__name__}: {str(e)[:200]}"
                log(f"   {plat}: {'OK ' + pid if pid else 'FAILED ' + err}")
                if pid:
                    done[plat] = pid
            m["posted"] = done
            m["post_at"] = (dt.datetime.now(tz) if when == "now" else when).isoformat()
            complete = all(p in done for p, _, _ in target)
            if complete:
                m.pop("when", None)
            write_json(mp, m)
            if complete:
                for ext in (".mp4", ".json"):
                    os.replace(os.path.join(rdy, name + ext), os.path.join(chdir, "scheduled", name + ext))
            else:
                bad += 1
    sys.exit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel", nargs="?"); ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    cfg = load_config(); tz = tzinfo(cfg); log = make_logger(tz, "autopost.log")
    lock = os.path.join(Q, "autopost.lock")                  # one run at a time: a second run would double-post
    if not a.dry:
        if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 1800:
            print("another autopost run is active; exiting"); sys.exit(0)
        open(lock, "w").write(str(os.getpid()))
    try:
        run(a, cfg, tz, log)
    finally:
        if not a.dry and os.path.exists(lock):
            os.remove(lock)


if __name__ == "__main__":
    main()
