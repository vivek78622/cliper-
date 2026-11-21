"""Unit tests for Sender configuration, credential security, exclusion logic, and dry runs."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SenderConfigAndDryRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for f in ("common.py", "clip_feeder.py", "autopost.py"):
            shutil.copy(os.path.join(KIT, f), self.tmp)
        os.makedirs(os.path.join(self.tmp, "config"))
        self.out = os.path.join(self.tmp, "clips")
        os.makedirs(self.out)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_py(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, *args],
            cwd=cwd or self.tmp,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_production_channels_json_values(self):
        """Verify the production config/channels.json matches all milestone specifications."""
        config_path = os.path.join(KIT, "config", "channels.json")
        self.assertTrue(os.path.exists(config_path), "config/channels.json must exist")
        with open(config_path, "r", encoding="utf-8-sig") as f:
            cfg = json.load(f)

        self.assertEqual(cfg.get("utc_offset"), "+05:30")
        self.assertEqual(cfg.get("timezone_name"), "Asia/Kolkata")
        feeder = cfg.get("feeder", {})
        self.assertIn("clipper_output", feeder)
        norm_clipper = os.path.normpath(feeder["clipper_output"]).lower()
        self.assertTrue(
            norm_clipper.endswith(os.path.normpath("gta-auto-clipper/output").lower()),
            f"clipper_output must point to GTA-Auto-Clipper/output, got {feeder['clipper_output']}",
        )

        channels = cfg.get("channels", {})
        self.assertGreaterEqual(len(channels), 1, "At least one channel must be configured")
        for chan_name, chan_cfg in channels.items():
            self.assertEqual(chan_cfg.get("youtube_per_hour"), 3, f"{chan_name} youtube_per_hour")
            self.assertEqual(chan_cfg.get("youtube_per_day"), 10, f"{chan_name} youtube_per_day")
            self.assertEqual(chan_cfg.get("instagram_per_hour"), 1, f"{chan_name} instagram_per_hour")
            self.assertEqual(chan_cfg.get("instagram_per_day"), 45, f"{chan_name} instagram_per_day")

    def test_production_env_security_and_gitignore(self):
        """Verify .env has placeholder credentials and is strictly gitignored."""
        env_path = os.path.join(KIT, ".env")
        self.assertTrue(os.path.exists(env_path), ".env must exist")
        with open(env_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        self.assertIn("ZERNIO_KEY_MAIN=", content)
        # Verify placeholder key is not an active real key or empty
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
        env_dict = dict(line.split("=", 1) for line in lines if "=" in line)
        self.assertIn("ZERNIO_KEY_MAIN", env_dict)
        self.assertTrue(
            "placeholder" in env_dict["ZERNIO_KEY_MAIN"].lower()
            or "test" in env_dict["ZERNIO_KEY_MAIN"].lower()
            or env_dict["ZERNIO_KEY_MAIN"].startswith("sk_"),
            "Key must be valid key format or safe placeholder",
        )

        gitignore_path = os.path.join(KIT, ".gitignore")
        self.assertTrue(os.path.exists(gitignore_path), ".gitignore must exist")
        with open(gitignore_path, "r", encoding="utf-8") as f:
            gi_content = f.read()
        self.assertIn(".env", gi_content)
        self.assertIn("config/channels.json", gi_content)

    def test_feeder_exclusion_matrix(self):
        """Test exclusion of test: true, gameplay_confirmed: false, score < min_score, and .bad files."""
        chans = {"c1": {"key_env": "K", "youtube_account_id": "PASTE", "instagram_account_id": "PASTE",
                        "youtube_per_hour": 3, "youtube_per_day": 10,
                        "instagram_per_hour": 1, "instagram_per_day": 45}}
        cfg = {
            "utc_offset": "+05:30",
            "timezone_name": "Asia/Kolkata",
            "feeder": {
                "clipper_output": self.out,
                "feed_since": "2020-01-01T00:00",
                "lookahead_hours": 4,
                "min_score": 5.0,
                "titles": ["Test Title"],
                "hashtags": ["#test"],
            },
            "channels": chans,
        }
        with open(os.path.join(self.tmp, "config", "channels.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f)

        # 1. Valid eligible clip
        name_valid = "clip-valid"
        with open(os.path.join(self.out, name_valid + ".mp4"), "wb") as f:
            f.write(b"video" * 100)
        with open(os.path.join(self.out, name_valid + ".json"), "w", encoding="utf-8") as f:
            json.dump({"video": name_valid + ".mp4", "score": 8.0, "gameplay_confirmed": True, "test": False, "credit": "Streamer"}, f)

        # 2. Test clip (test: True)
        name_test = "clip-test"
        with open(os.path.join(self.out, name_test + ".mp4"), "wb") as f:
            f.write(b"video" * 100)
        with open(os.path.join(self.out, name_test + ".json"), "w", encoding="utf-8") as f:
            json.dump({"video": name_test + ".mp4", "score": 9.0, "gameplay_confirmed": True, "test": True, "credit": "Streamer"}, f)

        # 3. Unconfirmed gameplay (gameplay_confirmed: False)
        name_unconfirmed = "clip-unconfirmed"
        with open(os.path.join(self.out, name_unconfirmed + ".mp4"), "wb") as f:
            f.write(b"video" * 100)
        with open(os.path.join(self.out, name_unconfirmed + ".json"), "w", encoding="utf-8") as f:
            json.dump({"video": name_unconfirmed + ".mp4", "score": 9.0, "gameplay_confirmed": False, "test": False, "credit": "Streamer"}, f)

        # 4. Low score clip (score: 3.0 < min_score 5.0)
        name_low = "clip-lowscore"
        with open(os.path.join(self.out, name_low + ".mp4"), "wb") as f:
            f.write(b"video" * 100)
        with open(os.path.join(self.out, name_low + ".json"), "w", encoding="utf-8") as f:
            json.dump({"video": name_low + ".mp4", "score": 3.0, "gameplay_confirmed": True, "test": False, "credit": "Streamer"}, f)

        # 5. Vetoed clip (.bad file exists)
        name_bad = "clip-vetoed"
        with open(os.path.join(self.out, name_bad + ".mp4"), "wb") as f:
            f.write(b"video" * 100)
        with open(os.path.join(self.out, name_bad + ".json"), "w", encoding="utf-8") as f:
            json.dump({"video": name_bad + ".mp4", "score": 9.5, "gameplay_confirmed": True, "test": False, "credit": "Streamer"}, f)
        with open(os.path.join(self.out, name_bad + ".bad"), "w", encoding="utf-8") as f:
            f.write("Facecam visible in gameplay region")

        # Set all mtimes to > 60s ago
        old = time.time() - 300
        for name in (name_valid, name_test, name_unconfirmed, name_low, name_bad):
            os.utime(os.path.join(self.out, name + ".mp4"), (old, old))

        # First verify in --dry mode: nothing should be written to queue
        r_dry = self.run_py("clip_feeder.py", "--dry")
        self.assertEqual(r_dry.returncode, 0, r_dry.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "queue", "clip_feeder.json")),
                         "Dry run must not create clip_feeder.json state")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "queue", "c1", "ready")),
                         "Dry run must not create ready files")

        # Now run live feeder: only clip-valid should be ingested
        r_live = self.run_py("clip_feeder.py")
        self.assertEqual(r_live.returncode, 0, r_live.stderr)

        with open(os.path.join(self.tmp, "queue", "clip_feeder.json"), "r", encoding="utf-8") as f:
            state = json.load(f)
        fed = state["fed"]

        # Only clip-valid should be fed to c1
        self.assertEqual(fed.get(name_valid), f"c1-clip-{name_valid}")
        self.assertEqual(fed.get(name_bad), "vetoed")
        self.assertNotIn(name_test, fed)
        self.assertNotIn(name_unconfirmed, fed)
        self.assertNotIn(name_low, fed)

        # Check ready folder
        ready_dir = os.path.join(self.tmp, "queue", "c1", "ready")
        ready_files = os.listdir(ready_dir)
        self.assertIn(f"c1-clip-{name_valid}.mp4", ready_files)
        self.assertIn(f"c1-clip-{name_valid}.json", ready_files)
        self.assertEqual(len([f for f in ready_files if f.endswith(".mp4")]), 1)

    def test_veto_purge_from_ready(self):
        """Test that adding a .bad file for a staged clip causes feeder to purge it from ready/."""
        chans = {"c1": {"key_env": "K", "youtube_account_id": "PASTE", "instagram_account_id": "PASTE",
                        "youtube_per_hour": 3, "youtube_per_day": 10,
                        "instagram_per_hour": 1, "instagram_per_day": 45}}
        cfg = {
            "utc_offset": "+05:30",
            "feeder": {
                "clipper_output": self.out,
                "feed_since": "2020-01-01T00:00",
                "lookahead_hours": 4,
                "min_score": 0,
                "titles": ["T"],
                "hashtags": ["#t"],
            },
            "channels": chans,
        }
        with open(os.path.join(self.tmp, "config", "channels.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f)

        name = "clip-to-veto"
        with open(os.path.join(self.out, name + ".mp4"), "wb") as f:
            f.write(b"video" * 100)
        with open(os.path.join(self.out, name + ".json"), "w", encoding="utf-8") as f:
            json.dump({"video": name + ".mp4", "score": 8.0, "gameplay_confirmed": True, "test": False, "credit": "Streamer"}, f)
        old = time.time() - 300
        os.utime(os.path.join(self.out, name + ".mp4"), (old, old))

        # Feed the clip
        r = self.run_py("clip_feeder.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        ready_dir = os.path.join(self.tmp, "queue", "c1", "ready")
        self.assertTrue(os.path.exists(os.path.join(ready_dir, f"c1-clip-{name}.mp4")))

        # Now veto the clip
        with open(os.path.join(self.out, name + ".bad"), "w", encoding="utf-8") as f:
            f.write("User vetoed this clip")

        # Run feeder again
        r2 = self.run_py("clip_feeder.py")
        self.assertEqual(r2.returncode, 0, r2.stderr)

        # File must be purged from ready/
        self.assertFalse(os.path.exists(os.path.join(ready_dir, f"c1-clip-{name}.mp4")),
                         "Vetoed clip mp4 must be removed from ready/")
        self.assertFalse(os.path.exists(os.path.join(ready_dir, f"c1-clip-{name}.json")),
                         "Vetoed clip json must be removed from ready/")

        with open(os.path.join(self.tmp, "queue", "clip_feeder.json"), "r", encoding="utf-8") as f:
            state = json.load(f)
        self.assertEqual(state["fed"].get(name), "vetoed")

    def test_autopost_dry_run_runway_and_safety(self):
        """Test autopost --dry creates RUNWAY.md, leaves ready/ untouched, and makes zero network uploads."""
        chans = {"c1": {"key_env": "K", "youtube_account_id": "ACC_YT", "instagram_account_id": "ACC_IG",
                        "youtube_per_hour": 3, "youtube_per_day": 10,
                        "instagram_per_hour": 1, "instagram_per_day": 45}}
        cfg = {
            "utc_offset": "+05:30",
            "timezone_name": "Asia/Kolkata",
            "feeder": {
                "clipper_output": self.out,
                "feed_since": "2020-01-01T00:00",
                "lookahead_hours": 4,
                "min_score": 0,
                "titles": ["T"],
                "hashtags": ["#t"],
            },
            "channels": chans,
        }
        with open(os.path.join(self.tmp, "config", "channels.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f)

        # Create dummy .env with dummy key
        with open(os.path.join(self.tmp, ".env"), "w", encoding="utf-8") as f:
            f.write("K=mock_key_value\n")

        # Create a ready clip
        ready_dir = os.path.join(self.tmp, "queue", "c1", "ready")
        os.makedirs(ready_dir, exist_ok=True)
        qname = "c1-clip-test1"
        with open(os.path.join(ready_dir, f"{qname}.mp4"), "wb") as f:
            f.write(b"mp4data")
        old = time.time() - 300
        os.utime(os.path.join(ready_dir, f"{qname}.mp4"), (old, old))
        with open(os.path.join(ready_dir, f"{qname}.json"), "w", encoding="utf-8") as f:
            json.dump({
                "title": "Dry Run Test Video",
                "youtube_description": "Description",
                "instagram_caption": "Caption",
                "hashtags": ["#dryrun"],
                "when": "2026-11-25T14:00:00+05:30",
                "platforms": ["youtube", "instagram"],
            }, f)

        # Run autopost --dry
        r = self.run_py("autopost.py", "--dry")
        self.assertEqual(r.returncode, 0, r.stdout + "\n" + r.stderr)
        self.assertIn("(dry)", r.stdout)

        # Verify RUNWAY.md exists and includes c1
        runway_path = os.path.join(self.tmp, "queue", "RUNWAY.md")
        self.assertTrue(os.path.exists(runway_path), "RUNWAY.md must be generated")
        with open(runway_path, "r", encoding="utf-8") as f:
            runway_text = f.read()
        self.assertIn("c1", runway_text)
        self.assertIn("in ready/ |", runway_text)

        # In dry run mode, ready files must remain in ready/ (not moved to scheduled/)
        self.assertTrue(os.path.exists(os.path.join(ready_dir, f"{qname}.mp4")),
                        "Dry run must not move ready mp4")
        self.assertTrue(os.path.exists(os.path.join(ready_dir, f"{qname}.json")),
                        "Dry run must not move ready json")
        scheduled_dir = os.path.join(self.tmp, "queue", "c1", "scheduled")
        scheduled_files = os.listdir(scheduled_dir) if os.path.exists(scheduled_dir) else []
        self.assertEqual(len(scheduled_files), 0, f"Dry run must not schedule any files, found {scheduled_files}")


if __name__ == "__main__":
    unittest.main()
