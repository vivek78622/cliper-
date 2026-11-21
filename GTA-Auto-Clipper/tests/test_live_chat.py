import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from live_chat import create_live_chat_collector, score_chat_windows


class LiveChatScoringTests(unittest.TestCase):
    def test_diverse_reaction_burst_scores_above_repeated_single_user_spam(self):
        burst = [
            {"t": 11 + i * 0.4, "user": f"viewer{i}", "text": "LOL no way 😂"}
            for i in range(8)
        ]
        spam = [
            {"t": 21 + i * 0.1, "user": "oneviewer", "text": "LOL no way 😂"}
            for i in range(30)
        ]
        rows = score_chat_windows(burst + spam, [0, 10, 20, 30], 10)
        by_start = {round(row["start"]): row for row in rows}
        self.assertGreater(by_start[10]["signal"], by_start[20]["signal"])
        self.assertGreater(by_start[10]["reactions"], 1)

    def test_youtube_chat_falls_back_when_api_key_is_missing(self):
        collector, source, reason = create_live_chat_collector(
            "https://www.youtube.com/watch?v=abc123XYZ89", environ={},
        )
        self.assertIsNone(collector)
        self.assertEqual(source, "unavailable")
        self.assertIn("YOUTUBE_API_KEY", reason)

    def test_twitch_chat_falls_back_when_login_is_missing(self):
        collector, source, reason = create_live_chat_collector(
            "https://www.twitch.tv/somechannel", environ={},
        )
        self.assertIsNone(collector)
        self.assertEqual(source, "unavailable")
        self.assertIn("TWITCH_CHAT_TOKEN", reason)


if __name__ == "__main__":
    unittest.main()
