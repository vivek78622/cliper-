r"""Schedule a finished clip to your connected YouTube and Instagram accounts.

Usage:  python publish.py output\gta-CLIP-ID --publish --unattended --scheduled-for FUTURE_ISO_TIME
Reads PUBLISH_API_KEY, PUBLISH_YOUTUBE_ACCOUNT_ID and PUBLISH_INSTAGRAM_ACCOUNT_ID from your private environment.
"""
import os

for new, old in (("PUBLISH_API_KEY", "ZERNIO_API_KEY"), ("PUBLISH_YOUTUBE_ACCOUNT_ID", "ZERNIO_YOUTUBE_ACCOUNT_ID"),
                 ("PUBLISH_INSTAGRAM_ACCOUNT_ID", "ZERNIO_INSTAGRAM_ACCOUNT_ID")):
    if os.environ.get(new) and not os.environ.get(old):
        os.environ[old] = os.environ[new]

import zernio_publish

if __name__ == "__main__":
    zernio_publish.main()
