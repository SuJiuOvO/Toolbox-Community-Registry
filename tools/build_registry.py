"""Validate all manifests before producing deterministic registry packages."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import zipfile

from jsonschema import Draft7Validator


BASE_DIR = Path(__file__).resolve().parent.parent
GITHUB_USER = "SuJiuOvO"
GITHUB_REPO = "Toolbox-Community-Registry"
GITEE_USER = "sujiuovo"
GITEE_REPO = "toolbox-community-registry"
DEFAULT_RELEASE_TAG = os.environ.get("TOOLBOX_RELEASE_TAG", "plugins")
QUICKJS_ENTRIES = ("entry.js", "index.js", "main.js", "tool.js")
# Normalize source/config files only; executable and media bytes are preserved.
TEXT_SUFFIXES = {".json", ".js", ".ts", ".rs", ".toml", ".lock", ".sh", ".bat", ".cmd", ".ps1", ".py", ".yaml", ".yml"}


def load_validator(schema_path: Path) -> Draft7Validator:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    return Draft7Validator(schema)


def validate_manifest(manifest: dict, plugin_path: Path, validator: Draft7Validator) -> None:
    errors = sorted(validator.iter_errors(manifest), key=lambda error: str(list(error.path)))
    if errors:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ValueError(f"Plugin {plugin_path.name} failed manifest schema: {details}")
    if manifest["id"] != plugin_path.name:
        raise ValueError(
            f"Plugin folder '{plugin_path.name}' does not match manifest id '{manifest['id']}'"
        )

    icon = manifest.get("icon")
    if isinstance(icon, dict):
        icon_data = icon.get("data", "")
        if icon.get("type") == "code" and len(icon_data.encode("utf-8")) > 64 * 1024:
            raise ValueError(f"Plugin {plugin_path.name} SVG code exceeds 64KB limit")
        if icon.get("type") in ("image", "file") and icon_data.startswith("data:image/"):
            if len(icon_data) > icon.get("maxSizeBytes", 512 * 1024) * 2:
                raise ValueError(f"Plugin {plugin_path.name} inline image exceeds size limit")

    # Match PluginManifest.isQuickJsPlugin and QuickJsBridgeService source lookup.
    execution_type = manifest.get("executionType", "")
    is_quickjs = (
        execution_type == "quickjs"
        or (execution_type == "script" and not manifest.get("nativeRunner"))
        or manifest.get("engineType") == "quickjs"
    )
    if is_quickjs:
        params = manifest.get("action", {}).get("params", {})
        if "scriptFile" in params:
            raise ValueError(
                f"Plugin {plugin_path.name} action.params.scriptFile is ignored by the client; "
                "use params.script or entry.js/index.js/main.js/tool.js"
            )
        script = params.get("script")
        if not (isinstance(script, str) and script.strip()) and not any(
            (plugin_path / name).is_file() for name in QUICKJS_ENTRIES
        ):
            raise ValueError(f"Plugin {plugin_path.name} has no QuickJS source (params.script or entry.js)")


def package_plugin(plugin_path: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for root, directories, files in os.walk(plugin_path):
            directories[:] = sorted(
                directory for directory in directories
                if directory != "target" and not directory.startswith(".")
            )
            for name in sorted(files):
                if name.endswith(".md") or (name.startswith(".") and name != ".gitkeep"):
                    continue
                path = Path(root) / name
                data = path.read_bytes()
                if path.suffix.lower() in TEXT_SUFFIXES:
                    data = data.replace(b"\r\n", b"\n")
                info = zipfile.ZipInfo(path.relative_to(plugin_path).as_posix(), (2026, 1, 1, 0, 0, 0))
                # Keep the established CI package format, independent of the host OS.
                info.create_system = 3
                info.external_attr = 0o600 << 16
                info.compress_type = zipfile.ZIP_STORED
                archive.writestr(info, data)
    return buffer.getvalue()


def write_if_changed(path: Path, data: bytes) -> None:
    if path.is_file() and path.read_bytes() == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def build_registry(
    base_dir: Path = BASE_DIR,
    *,
    validate_only: bool = False,
    release_tag: str = DEFAULT_RELEASE_TAG,
) -> int:
    base_dir = Path(base_dir)
    validator = load_validator(base_dir / "schemas" / "manifest.schema.json")
    plugins = []
    for plugin_path in sorted((base_dir / "plugins").iterdir()):
        manifest_path = plugin_path / "manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validate_manifest(manifest, plugin_path, validator)
        plugins.append((plugin_path, manifest))
    if validate_only:
        return len(plugins)

    # Stage every artifact in memory; a validation/packaging failure writes nothing.
    outputs = []
    index_plugins = []
    for plugin_path, manifest in plugins:
        plugin_id = manifest["id"]
        data = package_plugin(plugin_path)
        outputs.append((base_dir / "packages" / f"{plugin_id}.zip", data))
        entry = dict(manifest)
        entry.update(size=len(data), md5=hashlib.md5(data).hexdigest(), sha256=hashlib.sha256(data).hexdigest())
        entry["isOfficial"] = manifest.get("isOfficial", True)

        # Multi-source mirror & Release CDN accelerated endpoints
        release_url = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/download/{release_tag}/{plugin_id}.zip"
        cdn_url = f"https://ghproxy.net/https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/download/{release_tag}/{plugin_id}.zip"
        gitee_url = f"https://gitee.com/{GITEE_USER}/{GITEE_REPO}/releases/download/{release_tag}/{plugin_id}.zip"

        entry["downloadUrls"] = {
            "gitee": gitee_url,
            "github_cdn": cdn_url,
            "github_raw": release_url,
            "github": release_url,
            "github_release": release_url,
        }
        entry["downloadUrl"] = cdn_url
        index_plugins.append(entry)

    index_path = base_dir / "registry" / "index.json"
    current = json.loads(index_path.read_text(encoding="utf-8"))
    current["plugins"] = index_plugins
    outputs.append((index_path, json.dumps(current, ensure_ascii=False, indent=2).encode("utf-8")))
    for path, data in outputs:
        write_if_changed(path, data)
    return len(plugins)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true", help="Validate without writing packages or index")
    parser.add_argument(
        "--release-tag",
        default=DEFAULT_RELEASE_TAG,
        help=f"GitHub release tag for hosted packages (default: {DEFAULT_RELEASE_TAG})",
    )
    args = parser.parse_args()
    count = build_registry(validate_only=args.validate_only, release_tag=args.release_tag)
    verb = "validated" if args.validate_only else "validated and processed"
    print(f"Successfully {verb} {count} plugins.")


if __name__ == "__main__":
    main()
