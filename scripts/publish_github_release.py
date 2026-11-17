#!/usr/bin/env python3
"""
Controller - Automated GitHub v2.0.0 Release Publisher
Publishes release tag, metadata, release notes, and uploads release binaries and zip archives.
"""

import os
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path

REPO = "UnityNimit/controller"
TAG = "v2.0.0"
TITLE = "Controller v2.0.0: Tournament-Grade Precision & Zero Stick Drift"

def get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token and len(sys.argv) > 1 and sys.argv[1].startswith("ghp_"):
        token = sys.argv[1]
    if not token:
        print("\n[!] GITHUB_TOKEN not found in environment.")
        print("Usage:")
        print("  python scripts/publish_github_release.py <YOUR_GITHUB_PERSONAL_ACCESS_TOKEN>\n")
        print("Or set it in your shell:")
        print("  $env:GITHUB_TOKEN = 'ghp_your_token_here'")
        print("  python scripts/publish_github_release.py\n")
        sys.exit(1)
    return token.strip()

def main():
    token = get_token()
    base_dir = Path(__file__).resolve().parent.parent

    # Read release notes
    notes_path = base_dir / "documentation" / "RELEASE_NOTES_v2.0.0.md"
    body = notes_path.read_text(encoding="utf-8") if notes_path.exists() else "Controller v2.0.0 Release"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Controller-Release-Publisher",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    # 1. Create Release
    create_url = f"https://api.github.com/repos/{REPO}/releases"
    payload = {
        "tag_name": TAG,
        "target_commitish": "main",
        "name": TITLE,
        "body": body,
        "draft": False,
        "prerelease": False
    }

    print(f"Creating release {TAG} on {REPO}...")
    req = urllib.request.Request(create_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            rel_data = json.loads(resp.read().decode("utf-8"))
            release_id = rel_data["id"]
            html_url = rel_data["html_url"]
            print(f"[SUCCESS] Release created: {html_url} (ID: {release_id})")
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        if "already_exists" in err_msg:
            print("[INFO] Release already exists. Fetching existing release...")
            get_req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}", headers=headers)
            with urllib.request.urlopen(get_req) as resp:
                rel_data = json.loads(resp.read().decode("utf-8"))
                release_id = rel_data["id"]
                html_url = rel_data["html_url"]
                print(f"[INFO] Using existing release: {html_url} (ID: {release_id})")
        else:
            print(f"[ERROR] Failed to create release: {e.code} - {err_msg}")
            sys.exit(1)

    # 2. Upload Assets
    assets_to_upload = [
        ("Project-Controller.zip", base_dir / "build" / "Project-Controller.zip", "application/zip"),
        ("Controller.exe", base_dir / "dist" / "Controller.exe", "application/octet-stream"),
        ("Controller-Terminal.exe", base_dir / "dist" / "Controller-Terminal.exe", "application/octet-stream")
    ]

    for asset_name, asset_path, mime in assets_to_upload:
        if not asset_path.exists():
            print(f"[WARN] File {asset_path} does not exist, skipping.")
            continue

        file_size = os.path.getsize(asset_path)
        print(f"Uploading {asset_name} ({file_size / (1024*1024):.1f} MB)...")
        upload_url = f"https://uploads.github.com/repos/{REPO}/releases/{release_id}/assets?name={urllib.parse.quote(asset_name)}"
        upload_headers = headers.copy()
        upload_headers["Content-Type"] = mime
        upload_headers["Content-Length"] = str(file_size)

        with open(asset_path, "rb") as fh:
            data = fh.read()

        up_req = urllib.request.Request(upload_url, data=data, headers=upload_headers, method="POST")
        try:
            with urllib.request.urlopen(up_req) as up_resp:
                print(f"  [SUCCESS] Uploaded {asset_name} successfully.")
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="ignore")
            print(f"  [WARN] Upload for {asset_name} returned: {e.code} - {err}")

    print(f"\n[DONE] Release v2.0.0 is live at: {html_url}\n")

if __name__ == "__main__":
    main()
