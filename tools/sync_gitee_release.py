"""Synchronize built plugin packages to Gitee Release attachments via Open API."""

import argparse
import os
from pathlib import Path
import sys
from typing import Dict, Optional
import requests


DEFAULT_OWNER = "sujiuovo"
DEFAULT_REPO = "toolbox-community-registry"
DEFAULT_TAG = "plugins"
BASE_URL = "https://gitee.com/api/v5"


def get_or_create_release(
    session: requests.Session,
    owner: str,
    repo: str,
    tag: str,
    token: str,
) -> int:
    """Get the Gitee release ID for the given tag, or create one if it does not exist."""
    tag_url = f"{BASE_URL}/repos/{owner}/{repo}/releases/tags/{tag}"
    resp = session.get(tag_url, params={"access_token": token}, timeout=15)
    if resp.status_code == 200:
        data = resp.json()
        print(f"[INFO] Found existing Gitee release for tag '{tag}' (id={data['id']})")
        return data["id"]
    elif resp.status_code == 404:
        print(f"[INFO] Release for tag '{tag}' not found on Gitee, creating...")
        create_url = f"{BASE_URL}/repos/{owner}/{repo}/releases"
        payload = {
            "access_token": token,
            "tag_name": tag,
            "name": f"Community Plugins Release Assets ({tag})",
            "body": "Multi-Toolbox 社区功能模块云端 Release 镜像分发",
            "prerelease": False,
        }
        create_resp = session.post(create_url, json=payload, timeout=15)
        if create_resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to create Gitee release '{tag}': {create_resp.status_code} - {create_resp.text}"
            )
        data = create_resp.json()
        print(f"[INFO] Successfully created Gitee release '{tag}' (id={data['id']})")
        return data["id"]
    else:
        raise RuntimeError(
            f"Failed to query Gitee release '{tag}': {resp.status_code} - {resp.text}"
        )


def list_existing_attachments(
    session: requests.Session,
    owner: str,
    repo: str,
    release_id: int,
    token: str,
) -> Dict[str, int]:
    """Retrieve existing attachments for the release, mapping filename to attachment id."""
    url = f"{BASE_URL}/repos/{owner}/{repo}/releases/{release_id}/attach_files"
    page = 1
    attachments: Dict[str, int] = {}
    while True:
        resp = session.get(
            url,
            params={"access_token": token, "page": page, "per_page": 100},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[WARN] Failed to list attachments: {resp.status_code} - {resp.text}")
            break
        items = resp.json()
        if not items or not isinstance(items, list):
            break
        for item in items:
            name = item.get("name")
            att_id = item.get("id")
            if name and att_id:
                attachments[name] = att_id
        if len(items) < 100:
            break
        page += 1
    return attachments


def delete_attachment(
    session: requests.Session,
    owner: str,
    repo: str,
    release_id: int,
    attach_id: int,
    token: str,
) -> bool:
    """Delete an existing attachment from the Gitee release."""
    url = f"{BASE_URL}/repos/{owner}/{repo}/releases/{release_id}/attach_files/{attach_id}"
    resp = session.delete(url, params={"access_token": token}, timeout=15)
    return resp.status_code in (200, 204)


def upload_attachment(
    session: requests.Session,
    owner: str,
    repo: str,
    release_id: int,
    file_path: Path,
    token: str,
) -> bool:
    """Upload a file attachment to the Gitee release."""
    url = f"{BASE_URL}/repos/{owner}/{repo}/releases/{release_id}/attach_files"
    with file_path.open("rb") as f:
        files = {"file": (file_path.name, f, "application/zip")}
        data = {"access_token": token}
        resp = session.post(url, data=data, files=files, timeout=60)
    if resp.status_code in (200, 201):
        return True
    print(f"[ERROR] Failed to upload {file_path.name}: {resp.status_code} - {resp.text}")
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
    release_id = get_or_create_release(session, owner, repo, tag, token)
    existing_map = list_existing_attachments(session, owner, repo, release_id, token)
    print(f"[*] Found {len(existing_map)} existing attachment(s) in release.")

    uploaded_count = 0
    for file_path in zip_files:
        filename = file_path.name
        if filename in existing_map:
            print(f"[*] Deleting outdated Gitee attachment: {filename} (id={existing_map[filename]})")
            delete_attachment(session, owner, repo, release_id, existing_map[filename], token)

        print(f"[*] Uploading {filename} ({file_path.stat().st_size} bytes) to Gitee...")
        if upload_attachment(session, owner, repo, release_id, file_path, token):
            uploaded_count += 1
            print(f"[PASS] Successfully uploaded {filename}")
        else:
            print(f"[FAIL] Could not upload {filename}")

    print(f"[DONE] Successfully synchronized {uploaded_count}/{len(zip_files)} packages to Gitee Release.")
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
