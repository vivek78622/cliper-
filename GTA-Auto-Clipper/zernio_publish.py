"""Schedule one reviewed clip to YouTube and Instagram through Zernio.

Dry-run by default. Publishing requires --publish; posting unreviewed metadata
also requires the explicit unattended configuration described in the README.
"""
import argparse
import datetime as dt
import json
import os
import sys
import uuid
from pathlib import Path

import requests

API = "https://zernio.com/api/v1"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
PLATFORMS = (
    ("youtube", "ZERNIO_YOUTUBE_ACCOUNT_ID"),
    ("instagram", "ZERNIO_INSTAGRAM_ACCOUNT_ID"),
)


def load_metadata(path):
    with path.open(encoding="utf-8") as file:
        metadata = json.load(file)
    if not metadata.get("title") or not metadata.get("youtube_description") or not metadata.get("instagram_caption"):
        raise ValueError("metadata needs a title, YouTube description, and Instagram caption")
    if metadata.get("test"):
        raise ValueError("test clips cannot be published")
    return metadata


def scheduled_local_time(value):
    when = dt.datetime.fromisoformat(value)
    if when.tzinfo is None:
        raise ValueError("schedule time must include a timezone offset, e.g. 2026-11-18T12:00:00+05:30")
    return when.astimezone(IST).replace(tzinfo=None).isoformat(timespec="seconds")


def post_body(metadata, public_url, accounts, schedule):
    platforms = []
    for platform, account_id in accounts:
        entry = {"platform": platform, "accountId": account_id}
        if platform == "youtube":
            entry["customContent"] = metadata["youtube_description"]
            entry["platformSpecificData"] = {
                "title": metadata["title"][:100],
                "visibility": "public",
                "categoryId": "20",
                "madeForKids": False,
            }
        else:
            entry["customContent"] = metadata["instagram_caption"]
        platforms.append(entry)
    body = {
        "content": metadata["instagram_caption"],
        "mediaItems": [{"url": public_url, "type": "video"}],
        "platforms": platforms,
        "timezone": "Asia/Kolkata",
    }
    if schedule == "now":
        body["publishNow"] = True
    else:
        body["scheduledFor"] = schedule
    return body


def upload_and_schedule(video_path, metadata_path, metadata, accounts, schedule, api_key):
    headers = {"Authorization": f"Bearer {api_key}"}
    with video_path.open("rb") as file:
        size = os.fstat(file.fileno()).st_size
    presign = requests.post(
        f"{API}/media/presign", headers=headers,
        json={"filename": video_path.name, "contentType": "video/mp4", "size": size}, timeout=60,
    )
    presign.raise_for_status()
    upload = presign.json()
    with video_path.open("rb") as file:
        requests.put(upload["uploadUrl"], data=file, headers={"Content-Type": "video/mp4"}, timeout=900).raise_for_status()

    idempotency_key = metadata.get("zernio_idempotency_key") or str(uuid.uuid4())
    metadata["zernio_idempotency_key"] = idempotency_key
    with metadata_path.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
    response = requests.post(
        f"{API}/posts", headers={**headers, "Idempotency-Key": idempotency_key},
        json=post_body(metadata, upload["publicUrl"], accounts, schedule), timeout=300,
    )
    response.raise_for_status()
    result = response.json().get("post", {})
    post_id = result.get("_id")
    if not post_id:
        raise RuntimeError("Zernio did not return a post ID; check the Zernio dashboard before retrying")
    metadata["zernio_post_id"] = post_id
    metadata["zernio_status"] = result.get("status", "accepted")
    metadata["scheduled_for"] = result.get("scheduledFor") or schedule
    with metadata_path.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
    return result


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clip", type=Path, help="clip path without extension or path to its .mp4/.json")
    parser.add_argument("--scheduled-for", help="ISO time with offset, for example 2026-11-18T12:00:00+05:30")
    parser.add_argument("--now", action="store_true", help="publish immediately instead of scheduling")
    parser.add_argument("--publish", action="store_true", help="send the post to Zernio; otherwise only preview")
    parser.add_argument("--unattended", action="store_true", help="allow unreviewed metadata after one-time opt-in")
    args = parser.parse_args()
    base = args.clip.with_suffix("") if args.clip.suffix.lower() in {".mp4", ".json"} else args.clip
    video_path, metadata_path = base.with_suffix(".mp4"), base.with_suffix(".json")
    if not video_path.is_file() or not metadata_path.is_file():
        sys.exit("Clip files not found. Expected matching .mp4 and .json files.")
    try:
        metadata = load_metadata(metadata_path)
        schedule = "now" if args.now else (scheduled_local_time(args.scheduled_for) if args.scheduled_for else None)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        sys.exit(str(error))
    if args.now and args.scheduled_for:
        sys.exit("Use either --now or --scheduled-for, not both.")
    if args.unattended and args.now:
        sys.exit("Unattended mode only schedules future posts; it cannot publish immediately.")
    if args.publish and not schedule:
        sys.exit("Choose --scheduled-for or --now before publishing.")
    if metadata.get("zernio_post_id"):
        sys.exit(f"This clip already has a Zernio post ID ({metadata['zernio_post_id']}); check its status before retrying.")
    if not metadata.get("approved") and not args.unattended:
        sys.exit("Clip metadata is not approved. Review it, or configure unattended posting and pass --unattended.")
    if args.unattended and os.environ.get("GTA_UNATTENDED_POSTS") != "1":
        sys.exit("Set GTA_UNATTENDED_POSTS=1 in your private environment to enable unattended publishing.")
    accounts = [(platform, os.environ.get(variable, "")) for platform, variable in PLATFORMS]
    accounts = [(platform, account) for platform, account in accounts if account]
    if args.publish and not accounts:
        sys.exit("Set ZERNIO_YOUTUBE_ACCOUNT_ID and/or ZERNIO_INSTAGRAM_ACCOUNT_ID in your environment.")
    api_key = os.environ.get("ZERNIO_API_KEY")
    if args.publish and not api_key:
        sys.exit("Set ZERNIO_API_KEY in your private environment. Do not put it in a prompt or source file.")

    destinations = ', '.join(p for p, _ in accounts) or 'YouTube + Instagram (account IDs not configured)'
    plan = f"{base.name}: {schedule or 'DRY RUN — no schedule sent'} -> {destinations}"
    print(plan)
    if not args.publish:
        print("No post sent. Add --publish to schedule or publish this clip.")
        return
    try:
        post = upload_and_schedule(video_path, metadata_path, metadata, accounts, schedule, api_key)
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else "unknown"
        sys.exit(f"Zernio returned HTTP {status}. Check the Zernio dashboard before retrying.")
    except requests.RequestException as error:
        sys.exit(f"Zernio request failed ({type(error).__name__}). Check the Zernio dashboard before retrying.")
    print(f"Zernio accepted post {post['_id']} with status {post.get('status', 'accepted')}.")


if __name__ == "__main__":
    main()
