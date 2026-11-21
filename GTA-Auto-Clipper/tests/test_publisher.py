import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from zernio_publish import post_body, scheduled_local_time


class ZernioPublisherTests(unittest.TestCase):
    def test_scheduled_time_is_converted_to_ist(self):
        self.assertEqual(scheduled_local_time('2026-11-18T06:30:00+00:00'), '2026-11-18T12:00:00')

    def test_one_post_uses_both_accounts_and_platform_specific_copy(self):
        metadata = {
            'title': 'GTA moment',
            'youtube_description': 'YouTube copy',
            'instagram_caption': 'Instagram copy',
        }
        body = post_body(
            metadata,
            'https://media.example/clip.mp4',
            [('youtube', 'yt-account'), ('instagram', 'ig-account')],
            '2026-11-18T12:00:00',
        )
        self.assertEqual([p['platform'] for p in body['platforms']], ['youtube', 'instagram'])
        self.assertEqual(body['platforms'][0]['customContent'], 'YouTube copy')
        self.assertEqual(body['platforms'][1]['customContent'], 'Instagram copy')
        self.assertEqual(body['mediaItems'][0]['url'], 'https://media.example/clip.mp4')
        self.assertEqual(body['scheduledFor'], '2026-11-18T12:00:00')


if __name__ == '__main__':
    unittest.main()
