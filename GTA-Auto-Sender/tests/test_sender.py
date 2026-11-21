"""Offline test: fake clips -> clip_feeder -> equal split across channels -> autopost --dry. Sends nothing, needs no keys.
Run:  python -m unittest discover -s tests -p "test_*.py"
"""
import collections, datetime as dt, json, os, shutil, subprocess, sys, tempfile, time, unittest

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for f in ("common.py", "clip_feeder.py", "autopost.py"):
            shutil.copy(os.path.join(KIT, f), self.tmp)
        os.makedirs(os.path.join(self.tmp, "config")); self.out = os.path.join(self.tmp, "clips"); os.makedirs(self.out)
        chans = {f"c{i}": {"key_env": "K", "youtube_account_id": "PASTE", "instagram_account_id": "PASTE",
                           "youtube_per_hour": 12, "instagram_per_hour": 2} for i in (1, 2, 3)}
        cfg = {"utc_offset": "+00:00", "feeder": {"clipper_output": self.out, "lookahead_hours": 2,
               "titles": ["t"], "hashtags": ["#a"]}, "channels": chans}
        # a BOM on purpose: must not crash (PowerShell writes one by default)
        with open(os.path.join(self.tmp, "config", "channels.json"), "w", encoding="utf-8-sig") as f:
            f.write(json.dumps(cfg))
        for n in range(9):
            name = f"gta-{n}"
            with open(os.path.join(self.out, name + ".mp4"), "wb") as f:
                f.write(b"x" * 100)
            with open(os.path.join(self.out, name + ".json"), "w", encoding="utf-8") as f:
                json.dump({"video": name + ".mp4", "score": 5 - n * 0.1, "gameplay_confirmed": True, "credit": "Streamer"}, f)
            old = time.time() - 600
            os.utime(os.path.join(self.out, name + ".mp4"), (old, old))
        # a test clip, a non-gameplay clip and a vetoed clip must never be fed
        for name, extra in (("test-1", {"test": True}), ("menu-1", {"gameplay_confirmed": False}), ("bad-1", {})):
            with open(os.path.join(self.out, name + ".mp4"), "wb") as f:
                f.write(b"x")
            old = time.time() - 600
            os.utime(os.path.join(self.out, name + ".mp4"), (old, old))
            with open(os.path.join(self.out, name + ".json"), "w", encoding="utf-8") as f:
                json.dump({"video": name + ".mp4", "score": 9, "gameplay_confirmed": True, **extra}, f)
        with open(os.path.join(self.out, "bad-1.bad"), "w", encoding="utf-8") as f:
            f.write("facecam visible")

    def run_py(self, *args):
        return subprocess.run([sys.executable, *args], cwd=self.tmp, capture_output=True, text=True, timeout=120)

    def test_equal_split_and_vetoes(self):
        r = self.run_py("clip_feeder.py"); self.assertEqual(r.returncode, 0, r.stderr)
        counts = collections.Counter()
        for c in ("c1", "c2", "c3"):
            d = os.path.join(self.tmp, "queue", c, "ready")
            counts[c] = len([f for f in os.listdir(d) if f.endswith(".mp4")]) if os.path.isdir(d) else 0
        self.assertEqual(sum(counts.values()), 9, counts)
        self.assertEqual(set(counts.values()), {3}, f"unequal split: {counts}")
        with open(os.path.join(self.tmp, "queue", "clip_feeder.json"), encoding="utf-8") as f:
            fed = json.load(f)["fed"]
        for name in ("test-1", "menu-1"):
            self.assertNotIn(name, fed)
        self.assertEqual(fed["bad-1"], "vetoed")

    def test_youtube_daily_cap_sends_surplus_to_instagram(self):
        # 1 channel, 12 YouTube slots an hour, cap 2 a day: only 2 clips may go to YouTube, the rest Instagram-only
        cfgp = os.path.join(self.tmp, "config", "channels.json")
        with open(cfgp, "r", encoding="utf-8-sig") as f:
            cfg = json.loads(f.read())
        cfg["channels"] = {"c1": {**cfg["channels"]["c1"], "youtube_per_day": 2, "instagram_per_day": 3}}
        with open(cfgp, "w", encoding="utf-8") as f:
            f.write(json.dumps(cfg))
        self.run_py("clip_feeder.py")
        yt = ig = 0
        d = os.path.join(self.tmp, "queue", "c1", "ready")
        for f in os.listdir(d):
            if f.endswith(".json"):
                with open(os.path.join(d, f), "r", encoding="utf-8") as jf:
                    pl = json.load(jf)["platforms"]
                yt += "youtube" in pl; ig += "instagram" in pl
        self.assertEqual(yt, 2); self.assertEqual(ig, 3)

    def test_example_config_is_valid_json(self):
        with open(os.path.join(KIT, "config", "channels.example.json"), "r", encoding="utf-8") as f:
            json.load(f)

    def test_autopost_dry_runs_clean(self):
        self.run_py("clip_feeder.py")
        r = self.run_py("autopost.py", "--dry"); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
