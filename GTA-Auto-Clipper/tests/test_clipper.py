import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clip import (
    write_ass,
    build_video_filter, choose_crop_offset, choose_vertical_game_roi, gameplay_crop_offset, reaction_score,
    should_apply_smart_crop,
    source_identity, select_clip_start,
    DEFAULT_MAX_SECONDS, pick_moments, mask_word, ytdlp_cmd,
)


class ClipperReleaseTests(unittest.TestCase):
    def test_fit_layout_keeps_the_full_source_over_a_blurred_background(self):
        graph = build_video_filter('captions.ass', layout='fit')
        self.assertIn('[b]scale=1080:-2[fg]', graph)
        self.assertIn('overlay=(W-w)/2:(H-h)/2', graph)
        self.assertIn('boxblur=30:5', graph)

    def test_fill_layout_covers_the_whole_vertical_frame(self):
        graph = build_video_filter('captions.ass', layout='fill')
        self.assertIn('force_original_aspect_ratio=increase,crop=1080:1920:(iw-1080)*0.5000', graph)
        self.assertNotIn('boxblur', graph)

    def test_fill_layout_with_a_gameplay_roi_still_fills_the_screen(self):
        graph = build_video_filter('captions.ass', layout='fill', source_roi=(0, 150, 360, 389))
        self.assertTrue(graph.startswith('[0:v]crop=360:389:0:150,scale=1080:1920:force_original_aspect_ratio=increase'))
        self.assertNotIn('boxblur', graph)

    def test_gameplay_crop_centres_the_over_the_shoulder_player_anchor(self):
        for width, height in ((1920, 1080), (640, 360)):
            offset = gameplay_crop_offset(width, height, player_x=width * 0.38)
            crop_width = height * 9 / 16
            available = width - crop_width
            crop_center = offset * available + crop_width / 2
            self.assertAlmostEqual(crop_center, width * 0.38)

    def test_corner_facecam_outside_the_centre_keeps_the_character_centred(self):
        # A top-right facecam outside the player crop must not slide the crop to the edge.
        self.assertAlmostEqual(choose_crop_offset(1280, 720, [[(1100, 40, 80, 90)] for _ in range(5)]), gameplay_crop_offset(1280, 720, 1280 * 0.38))
        self.assertAlmostEqual(choose_crop_offset(1920, 1080, [[(180, 90, 70, 70)] for _ in range(4)]), gameplay_crop_offset(1920, 1080, 1920 * 0.38))

    def test_in_game_faces_never_move_the_crop(self):
        self.assertEqual(choose_crop_offset(1920, 1080, [[(1450, 300, 320, 420)] for _ in range(5)]), 0.5)
        self.assertEqual(choose_crop_offset(1920, 1080, [[(1670, 430, 90, 95)] for _ in range(5)]), 0.5)
        self.assertEqual(choose_crop_offset(1920, 1080, [[], [], []]), 0.5)

    def test_facecam_overlapping_the_centre_shifts_only_a_little(self):
        offset = choose_crop_offset(1920, 1080, [[(1180, 60, 90, 95)] for _ in range(5)])
        self.assertLess(offset, 0.5)
        self.assertGreater(offset, 0.2)

    def test_portrait_stack_uses_gameplay_below_a_persistent_top_facecam(self):
        samples = [[(140, 30, 70, 60)] for _ in range(5)]
        roi = choose_vertical_game_roi(360, 640, samples, active_bottom=540)
        self.assertIsNotNone(roi)
        x, y, width, height = roi
        self.assertEqual((x, width), (0, 360))
        self.assertGreaterEqual(y, 110)
        self.assertLessEqual(y + height, 540)

    def test_portrait_without_a_persistent_facecam_keeps_the_full_source(self):
        self.assertIsNone(choose_vertical_game_roi(360, 640, [[], [], []], 540))

    def test_uncertain_face_detection_falls_back_to_full_source_framing(self):
        self.assertFalse(should_apply_smart_crop(True, 0.5, None))
        self.assertTrue(should_apply_smart_crop(True, 1.0, None))
        self.assertTrue(should_apply_smart_crop(True, 0.5, (0, 120, 360, 420)))
        self.assertFalse(should_apply_smart_crop(False, 1.0, None))

    def test_generic_filler_words_do_not_count_as_a_strong_reaction(self):
        filler = [(0, 0.2, word) for word in 'oh no no okay here we go'.split()]
        self.assertEqual(reaction_score(filler), 0)

    def test_clear_reaction_phrases_score_above_filler(self):
        strong = [(0, 0.2, word) for word in 'holy shit that was insane'.split()]
        self.assertGreater(reaction_score(strong), 2)

    def test_unknown_creator_does_not_require_a_repository_allowlist(self):
        source = source_identity({'uploader': 'Creator', 'channel_id': 'UC-new'}, test=False)
        self.assertEqual(source['name'], 'Creator')
        self.assertFalse(source['test'])

    def test_live_capture_defaults_to_running_until_stopped(self):
        self.assertEqual(DEFAULT_MAX_SECONDS, 0)

    def test_highlight_starts_before_the_peak_and_stays_inside_the_chunk(self):
        self.assertAlmostEqual(select_clip_start(21.3, 6, 30, 90), 15.3)
        self.assertEqual(select_clip_start(2, 6, 30, 90), 0)
        self.assertEqual(select_clip_start(89, 6, 30, 90), 60)

    def test_each_selected_clip_uses_the_peak_inside_its_own_window(self):
        audio = np.full(90 * 16000, 0.01, dtype=np.float32)
        audio[20 * 16000:22 * 16000] = 0.8
        audio[60 * 16000:62 * 16000] = 0.8
        with patch('clip.load_audio', return_value=audio), patch('clip.whisper_words', return_value=[]):
            chosen, _ = pick_moments('unused.ts', clip_len=30, top=2, min_score=0, lead_in=6)
        starts = [start for _, start in chosen]
        self.assertEqual(len(starts), 2)
        self.assertEqual(len(set(starts)), 2)
        self.assertTrue(any(14 <= start <= 16 for start in starts), starts)
        self.assertTrue(any(54 <= start <= 56 for start in starts), starts)


class CaptionAndDownloaderTests(unittest.TestCase):
    def test_swear_words_are_masked_in_burned_captions(self):
        self.assertEqual(mask_word("shit"), "s***")
        self.assertEqual(mask_word("Fucking"), "F******")
        self.assertEqual(mask_word("Lucia"), "Lucia")
        self.assertEqual(mask_word("class"), "class")

    def test_ytdlp_uses_node_when_deno_is_missing(self):
        with patch("clip.shutil.which", side_effect=lambda name: "C:/node.exe" if name == "node" else None):
            cmd = ytdlp_cmd("-g", "URL")
        self.assertEqual(cmd[-4:], ["--js-runtimes", "node", "-g", "URL"])

    def test_ytdlp_leaves_default_runtime_when_deno_exists(self):
        with patch("clip.shutil.which", return_value="C:/deno.exe"):
            cmd = ytdlp_cmd("-g", "URL")
        self.assertNotIn("--js-runtimes", cmd)

class PopCaptionTests(unittest.TestCase):
    def _events(self, words):
        import tempfile, os
        from clip import WordTimings
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "c.ass")
            write_ass(path, WordTimings(words, "en", "English"), 0, 30, None, 400)
            return [l for l in open(path, encoding="utf-8").read().splitlines() if l.startswith("Dialogue: 0,")]

    @staticmethod
    def _secs(t):
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    def test_words_pop_in_yellow_one_at_a_time_without_karaoke_sweep(self):
        ev = self._events([(1.0, 1.3, "no"), (1.35, 1.6, "way"), (1.65, 2.0, "bro")])
        self.assertEqual(len(ev), 3)
        self.assertNotIn(r"\kf", "".join(ev))
        self.assertIn(r"\c&H00FFFF&", ev[0].split("NO")[0])          # first word yellow when spoken
        self.assertIn(r"\alpha&HFF&", ev[0].split("NO")[1])          # later words hidden until spoken
        self.assertIn(r"\c&HFFFFFF&", ev[2].split("NO")[0])          # earlier words turn white

    def test_caption_events_never_overlap_so_lines_never_stack(self):
        words = [(i * 0.25, i * 0.25 + 0.6, w) for i, w in enumerate(
            "what is happening right now this is insane look at that car go".split())]
        ev = self._events(words)
        spans = [(self._secs(e.split(",")[1]), self._secs(e.split(",")[2])) for e in ev]
        for (a0, a1), (b0, b1) in zip(spans, spans[1:]):
            self.assertLessEqual(a1, b0 + 1e-6)

    def test_phrases_stay_short_enough_for_one_line(self):
        ev = self._events([(i * 0.3, i * 0.3 + 0.25, w) for i, w in enumerate("absolutely unbelievable driving skills".split())])
        for e in ev:
            import re
            visible = re.sub(r"\{[^}]*\}", "", e.split(",,", 2)[-1].split(",,")[-1])
            self.assertLessEqual(len(visible), 24)


class SpokenLanguageLockTest(unittest.TestCase):
    def test_hindi_stream_locks_after_votes(self):
        import clip
        clip._forced_language = None
        clip._lang_votes = {"hi": 2, "en": 1}
        self.assertEqual(clip.locked_language(), "hi")

    def test_english_stream_stays_auto(self):
        import clip
        clip._forced_language = None
        clip._lang_votes = {"en": 5, "hi": 1}
        self.assertIsNone(clip.locked_language())

    def test_flag_forces(self):
        import clip
        clip._forced_language = "hi"
        self.assertEqual(clip.locked_language(), "hi")
        clip._forced_language = None
        clip._lang_votes = {}


class VetoAndTestFlagsTest(unittest.TestCase):
    def test_source_identity_preserves_test_flag(self):
        source = source_identity({"uploader": "local source"}, test=True)
        self.assertEqual(source["name"], "local source")
        self.assertTrue(source["test"])

    def test_veto_bad_file_matches_clip_naming(self):
        clip_name = "gta-20261121-174105-1"
        bad_file = Path(f"{clip_name}.bad")
        self.assertEqual(bad_file.stem, clip_name)
        self.assertEqual(bad_file.suffix, ".bad")


if __name__ == '__main__':
    unittest.main()

