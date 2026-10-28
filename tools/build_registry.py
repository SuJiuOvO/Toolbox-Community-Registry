import os
import json
import zipfile
import hashlib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGINS_DIR = os.path.join(BASE_DIR, "plugins")
PACKAGES_DIR = os.path.join(BASE_DIR, "packages")
REGISTRY_DIR = os.path.join(BASE_DIR, "registry")

os.makedirs(PACKAGES_DIR, exist_ok=True)
os.makedirs(REGISTRY_DIR, exist_ok=True)

GITHUB_USER = "SuJiuOvO"
GITHUB_REPO = "Toolbox-Community-Registry"
GITEE_USER = "sujiuovo"
GITEE_REPO = "toolbox-community-registry"

index_plugins = []

for plugin_id in sorted(os.listdir(PLUGINS_DIR)):
    plugin_path = os.path.join(PLUGINS_DIR, plugin_id)
    manifest_file = os.path.join(plugin_path, "manifest.json")
    if not os.path.isfile(manifest_file):
        continue

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 1. 校验必填字段
    for req in ["id", "name", "version", "category", "description"]:
        if req not in manifest:
            raise ValueError(f"Plugin {plugin_id} missing required field: {req}")

    if manifest["id"] != plugin_id:
        raise ValueError(f"Plugin folder '{plugin_id}' does not match manifest id '{manifest['id']}'")

    # 2. 校验平台配置
    platforms = manifest.get("platforms", ["universal"])
    if not isinstance(platforms, list) or not all(p in ["universal", "windows", "android"] for p in platforms):
        raise ValueError(f"Plugin {plugin_id} invalid platforms: {platforms}")

    # 3. 校验图标字段规范 (Manifest v2.0)
    raw_icon = manifest.get("icon")
    if isinstance(raw_icon, dict):
        icon_type = raw_icon.get("type", "image")
        if icon_type not in ["image", "code", "material", "default"]:
            raise ValueError(f"Plugin {plugin_id} invalid icon type '{icon_type}', must be image/code/material/default")
        icon_data = raw_icon.get("data") or raw_icon.get("content") or ""
        max_bytes = raw_icon.get("maxSizeBytes", 512 * 1024)
        if icon_type == "code" and len(icon_data) > 64 * 1024:
            raise ValueError(f"Plugin {plugin_id} SVG code exceeds 64KB limit")
        if icon_type == "image" and icon_data.startswith("data:image/") and len(icon_data) > max_bytes * 2:
            raise ValueError(f"Plugin {plugin_id} inline image exceeds size limit")

    # 4. 校验受控权限规范 (Manifest v2.4)
    perms = manifest.get("permissions")
    if perms is not None:
        if not isinstance(perms, list) or not all(isinstance(p, str) for p in perms):
            raise ValueError(f"Plugin {plugin_id} invalid permissions: {perms}, must be list of strings")

    # 5. 校验结果输出声明规范 (Manifest v2.4)
    outputs = manifest.get("outputs")
    if outputs is not None:
        if not isinstance(outputs, list):
            raise ValueError(f"Plugin {plugin_id} outputs must be a list")
        for out in outputs:
            if not isinstance(out, dict) or "id" not in out or "label" not in out:
                raise ValueError(f"Plugin {plugin_id} output item missing 'id' or 'label': {out}")

    zip_path = os.path.join(PACKAGES_DIR, f"{plugin_id}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(plugin_path):
            for file in sorted(files):
                if file.endswith(".md"):
                    continue
                file_full = os.path.join(root, file)
                rel_path = os.path.relpath(file_full, plugin_path).replace("\\", "/")
                parts = rel_path.split("/")
                if "target" in parts or any(p.startswith(".") and p != ".gitkeep" for p in parts):
                    continue
                with open(file_full, "rb") as f_in:
                    file_bytes = f_in.read()
                zinfo = zipfile.ZipInfo(rel_path, date_time=(2026, 1, 1, 0, 0, 0))
                z.writestr(zinfo, file_bytes)

    with open(zip_path, "rb") as zf:
        data = zf.read()
        md5_val = hashlib.md5(data).hexdigest()
        sha256_val = hashlib.sha256(data).hexdigest()

    entry = dict(manifest)
    entry["size"] = len(data)
    entry["md5"] = md5_val
    entry["sha256"] = sha256_val
    entry["isOfficial"] = manifest.get("isOfficial", True)
    entry["downloadUrls"] = {
        "gitee": f"https://gitee.com/{GITEE_USER}/{GITEE_REPO}/raw/main/packages/{plugin_id}.zip",
        "github_cdn": f"https://cdn.jsdelivr.net/gh/{GITHUB_USER}/{GITHUB_REPO}@main/packages/{plugin_id}.zip",
        "github": f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/packages/{plugin_id}.zip"
    }
    entry["downloadUrl"] = entry["downloadUrls"]["gitee"]
    index_plugins.append(entry)

registry_path = os.path.join(REGISTRY_DIR, "index.json")
with open(registry_path, "r", encoding="utf-8") as f:
    current = json.load(f)

current["plugins"] = index_plugins
with open(registry_path, "w", encoding="utf-8") as f:
    json.dump(current, f, ensure_ascii=False, indent=2)

print(f"Successfully validated and processed {len(index_plugins)} plugins.")
