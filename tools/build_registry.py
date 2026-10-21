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

    # 校验必填字段
    for req in ["id", "name", "version", "category", "description"]:
        if req not in manifest:
            raise ValueError(f"Plugin {plugin_id} missing required field: {req}")

    zip_path = os.path.join(PACKAGES_DIR, f"{plugin_id}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(plugin_path):
            for file in files:
                if file.endswith(".md"):
                    continue
                file_full = os.path.join(root, file)
                rel_path = os.path.relpath(file_full, plugin_path)
                z.write(file_full, rel_path)

    with open(zip_path, "rb") as zf:
        data = zf.read()
        md5_val = hashlib.md5(data).hexdigest()
        sha256_val = hashlib.sha256(data).hexdigest()

    entry = dict(manifest)
    entry["size"] = len(data)
    entry["md5"] = md5_val
    entry["sha256"] = sha256_val
    entry["downloadUrls"] = {
        "gitee": f"https://gitee.com/{GITEE_USER}/{GITEE_REPO}/raw/master/packages/{plugin_id}.zip",
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

print(f"Successfully processed {len(index_plugins)} plugins.")
