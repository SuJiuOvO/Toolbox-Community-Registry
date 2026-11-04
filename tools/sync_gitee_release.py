"""Synchronize built plugin packages to Gitee Release attachments via Open API."""

import argparse
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional
import requests


DEFAULT_OWNER = "sujiuovo"
DEFAULT_REPO = "toolbox-community-registry"
DEFAULT_TAG = "plugins"
BASE_URL = "https://gitee.com/api/v5"


def find_release_id_by_tag(
    session: requests.Session,
    owner: str,
    repo: str,
    tag: str,
    token: str,
) -> Optional[int]:
    """Locate release ID by tag using releases/tags or by listing all releases."""
    tag_url = f"{BASE_URL}/repos/{owner}/{repo}/releases/tags/{tag}"
    try:
        resp = session.get(tag_url, params={"access_token": token}, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and data.get("id"):
                return data["id"]
    except Exception as e:
        print(f"[WARN] Failed querying tag endpoint: {e}")

    # Fallback: query releases list
    try:
        all_releases = session.get(
            f"{BASE_URL}/repos/{owner}/{repo}/releases",
            params={"access_token": token, "per_page": 100},
            timeout=15,
        )
        if all_releases.status_code == 200:
            items = all_releases.json()
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and item.get("tag_name") == tag:
                        return item.get("id")
    except Exception as e:
        print(f"[WARN] Failed listing releases: {e}")

    return None


def delete_release(
    session: requests.Session,
    owner: str,
    repo: str,
    release_id: int,
    token: str,
) -> bool:
    """Delete a release container by id."""
    url = f"{BASE_URL}/repos/{owner}/{repo}/releases/{release_id}"
    resp = session.delete(url, params={"access_token": token}, timeout=15)
    return resp.status_code in (200, 204)


def create_release(
    session: requests.Session,
    owner: str,
    repo: str,
    tag: str,
    token: str,
) -> int:
    """Create a release for the specified tag."""
    create_url = f"{BASE_URL}/repos/{owner}/{repo}/releases"
    payload = {
        "access_token": token,
        "tag_name": tag,
        "name": f"Community Plugins Release Assets ({tag})",
        "body": "Multi-Toolbox 社区功能模块云端 Release 镜像分发",
        "prerelease": False,
        "target_commitish": "main",
    }
    create_resp = session.post(create_url, json=payload, timeout=15)
    if create_resp.status_code in (200, 201):
        data = create_resp.json()
        if isinstance(data, dict) and "id" in data:
            return data["id"]

    # If creation failed, check if it was created concurrently
    rel_id = find_release_id_by_tag(session, owner, repo, tag, token)
    if rel_id is not None:
        return rel_id

    raise RuntimeError(
        f"Failed to create Gitee release '{tag}': {create_resp.status_code} - {create_resp.text}"
    )


def upload_attachment(
    session: requests.Session,
    owner: str,
    repo: str,
    release_id: int,
    file_path: Path,
    token: str,
    retries: int = 3,
) -> bool:
    """Upload a file attachment to the Gitee release with retries."""
    url = f"{BASE_URL}/repos/{owner}/{repo}/releases/{release_id}/attach_files"
    for attempt in range(1, retries + 1):
        try:
            with file_path.open("rb") as f:
                files = {"file": (file_path.name, f, "application/zip")}
                data = {"access_token": token}
                resp = session.post(url, data=data, files=files, timeout=60)
            if resp.status_code in (200, 201):
                return True
            print(f"[WARN] Upload {file_path.name} attempt {attempt}/{retries} returned {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[WARN] Upload {file_path.name} attempt {attempt}/{retries} failed: {e}")
    return False


def sync_gitee_release(
    owner: str = DEFAULT_OWNER,
    repo: str = DEFAULT_REPO,
    tag: str = DEFAULT_TAG,
    packages_dir: Path = Path("packages"),
    token: Optional[str] = None,
    dry_run: bool = False,
) -> int:
    """Sync all package zip files in packages_dir to Gitee release."""
    if not token:
        token = os.environ.get("GITEE_TOKEN") or os.environ.get("GITEE_ACCESS_TOKEN")

    if not token:
        print("[INFO] GITEE_TOKEN is not configured; skipping Gitee release asset synchronization.")
        return 0

    packages_dir = Path(packages_dir)
    if not packages_dir.is_dir():
        print(f"[WARN] Packages directory '{packages_dir}' does not exist.")
        return 0

    zip_files = sorted(packages_dir.glob("*.zip"))
    if not zip_files:
        print(f"[INFO] No zip packages found in '{packages_dir}'.")
        return 0

    print(f"[*] Found {len(zip_files)} zip package(s) to synchronize to Gitee release '{tag}'.")
    if dry_run:
        for z in zip_files:
            print(f"[DRY-RUN] Would upload {z.name} to {owner}/{repo} (tag={tag})")
        return len(zip_files)

    session = requests.Session()
    existing_id = find_release_id_by_tag(session, owner, repo, tag, token)
    if existing_id is not None:
        print(f"[INFO] Found existing Gitee release (id={existing_id}). Recreating for clean asset sync...")
        delete_release(session, owner, repo, existing_id, token)

    release_id = create_release(session, owner, repo, tag, token)
    print(f"[INFO] Successfully active Gitee release id={release_id} for tag '{tag}'")

    uploaded_count = 0
    for file_path in zip_files:
        filename = file_path.name
        print(f"[*] Uploading {filename} ({file_path.stat().st_size} bytes) to Gitee...")
        if upload_attachment(session, owner, repo, release_id, file_path, token, retries=3):
            uploaded_count += 1
            print(f"[PASS] Successfully uploaded {filename}")
        else:
            print(f"[FAIL] Could not upload {filename}")

    print(f"[DONE] Successfully synchronized {uploaded_count}/{len(zip_files)} packages to Gitee Release.")
    if uploaded_count == 0 and len(zip_files) > 0:
        raise RuntimeError("Failed to upload any packages to Gitee Release attachments.")
    return uploaded_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", default=DEFAULT_OWNER, help=f"Gitee owner (default: {DEFAULT_OWNER})")
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"Gitee repository (default: {DEFAULT_REPO})")
    parser.add_argument("--tag", default=DEFAULT_TAG, help=f"Release tag name (default: {DEFAULT_TAG})")
    parser.add_argument("--dir", default="packages", help="Directory containing .zip packages")
    parser.add_argument("--token", default=None, help="Gitee Personal Access Token (or env GITEE_TOKEN)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate upload without network mutations")
    args = parser.parse_args()

    count = sync_gitee_release(
        owner=args.owner,
        repo=args.repo,
        tag=args.tag,
        packages_dir=Path(args.dir),
        token=args.token,
        dry_run=args.dry_run,
    )
    if count == 0 and not args.token and not os.environ.get("GITEE_TOKEN"):
        # Skipped due to no token is a non-error exit in CI
        sys.exit(0)


if __name__ == "__main__":
    main()
