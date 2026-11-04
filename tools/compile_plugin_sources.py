#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Toolbox Plugin Cross-Compilation Tool

Automatically compiles Rust / C++ source projects within plugins/ to:
  1. Windows native x86_64 binaries (bin/{id}.exe)
  2. WebAssembly WASI Preview 1 binaries (bin/{id}.wasm)

Used by local developers and GitHub Actions cross-compilation matrix.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_cargo_projects(plugins_dir: Path, target_plugin_id: str | None = None):
    """
    Scans plugins directory for plugins with Rust / Cargo sources.
    Returns list of dicts with plugin metadata.
    """
    projects = []
    if not plugins_dir.exists():
        return projects

    for entry in sorted(plugins_dir.iterdir()):
        if not entry.is_dir():
            continue

        plugin_id = entry.name
        if target_plugin_id and plugin_id != target_plugin_id:
            continue

        # Look for Cargo.toml at plugin/src/Cargo.toml or plugin/Cargo.toml
        cargo_dir = None
        if (entry / "src" / "Cargo.toml").is_file():
            cargo_dir = entry / "src"
        elif (entry / "Cargo.toml").is_file():
            cargo_dir = entry

        if not cargo_dir:
            continue

        manifest_path = entry / "manifest.json"
        manifest_data = {}
        if manifest_path.is_file():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
            except Exception as e:
                print(f"[WARN] Failed to parse {manifest_path}: {e}", file=sys.stderr)

        projects.append({
            "plugin_id": plugin_id,
            "plugin_dir": entry,
            "cargo_dir": cargo_dir,
            "manifest": manifest_data,
        })

    return projects


def get_target_entry(manifest: dict, target_type: str, plugin_id: str) -> str:
    """
    Extracts the destination binary path from manifest or applies standard convention.
    """
    if target_type == "windows":
        native_runner = manifest.get("nativeRunner") or {}
        entry = native_runner.get("entry")
        if not entry and manifest.get("executionType") == "native_windows":
            entry = manifest.get("action", {}).get("handler")
        return entry if entry else f"bin/{plugin_id}.exe"
    elif target_type == "wasm":
        wasm_runner = manifest.get("wasmRunner") or {}
        entry = wasm_runner.get("entry")
        if not entry and manifest.get("executionType") == "wasm":
            entry = manifest.get("action", {}).get("params", {}).get("module")
        return entry if entry else f"bin/{plugin_id}.wasm"
    else:
        raise ValueError(f"Unknown target_type: {target_type}")


def compile_cargo_project(
    project: dict,
    target_type: str,
    dry_run: bool = False,
    cargo_bin: str = "cargo",
) -> bool:
    """
    Compiles a single Cargo project for the given target type (windows or wasm).
    """
    plugin_id = project["plugin_id"]
    plugin_dir = project["plugin_dir"]
    cargo_dir = project["cargo_dir"]
    manifest = project["manifest"]

    dest_rel_path = get_target_entry(manifest, target_type, plugin_id)
    dest_path = plugin_dir / dest_rel_path

    print(f"\n========================================================")
    print(f"[*] Building plugin [{plugin_id}] for [{target_type}]")
    print(f"    Source Dir : {cargo_dir}")
    print(f"    Target Dest: {dest_path}")
    print(f"========================================================")

    if dry_run:
        print(f"[DRY-RUN] Would compile {cargo_dir} -> {dest_path}")
        return True

    if not shutil.which(cargo_bin):
        print(f"[ERROR] '{cargo_bin}' executable not found in PATH.", file=sys.stderr)
        return False

    if target_type == "windows":
        cmd = [cargo_bin, "build", "--release"]
    elif target_type == "wasm":
        cmd = [cargo_bin, "build", "--release", "--target", "wasm32-wasip1"]
    else:
        print(f"[ERROR] Unsupported target type: {target_type}", file=sys.stderr)
        return False

    print(f">>> Running: {' '.join(cmd)} (cwd={cargo_dir})")
    ret = subprocess.run(cmd, cwd=str(cargo_dir))
    if ret.returncode != 0:
        if target_type == "wasm":
            # Fallback to legacy target wasm32-wasi if wasm32-wasip1 is not yet installed
            fallback_cmd = [cargo_bin, "build", "--release", "--target", "wasm32-wasi"]
            print(f">>> Retrying with fallback target: {' '.join(fallback_cmd)}")
            ret = subprocess.run(fallback_cmd, cwd=str(cargo_dir))
            if ret.returncode != 0:
                print(f"[ERROR] Cargo build failed with exit code {ret.returncode}", file=sys.stderr)
                return False
        else:
            print(f"[ERROR] Cargo build failed with exit code {ret.returncode}", file=sys.stderr)
            return False

    # Locate generated output binary
    built_file = None
    if target_type == "windows":
        candidate_dir = cargo_dir / "target" / "release"
        if not candidate_dir.exists():
            candidate_dir = plugin_dir / "target" / "release"
        if candidate_dir.exists():
            for f in candidate_dir.iterdir():
                if f.is_file() and f.suffix.lower() == ".exe" and not f.name.endswith(".d"):
                    built_file = f
                    break
    elif target_type == "wasm":
        for target_subdir in ["wasm32-wasip1", "wasm32-wasi"]:
            candidate_dir = cargo_dir / "target" / target_subdir / "release"
            if not candidate_dir.exists():
                candidate_dir = plugin_dir / "target" / target_subdir / "release"
            if candidate_dir.exists():
                for f in candidate_dir.iterdir():
                    if f.is_file() and f.suffix.lower() == ".wasm" and not f.name.endswith(".d"):
                        built_file = f
                        break
            if built_file:
                break

    if not built_file or not built_file.is_file():
        print(f"[ERROR] Could not locate built binary in target directory for {plugin_id}", file=sys.stderr)
        return False

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built_file, dest_path)
    print(f"[SUCCESS] Copied artifact: {built_file.name} -> {dest_path} ({dest_path.stat().st_size} bytes)")
    return True


def validate_plugin_binaries(plugins_dir: Path) -> bool:
    """
    Checks that every plugin declaring nativeRunner or wasmRunner has its required binary in place.
    """
    projects = find_cargo_projects(plugins_dir)
    all_valid = True
    print(f"[*] Validating compiled binaries for {len(projects)} source plugins...")

    for p in projects:
        plugin_id = p["plugin_id"]
        plugin_dir = p["plugin_dir"]
        manifest = p["manifest"]

        has_native = "nativeRunner" in manifest or manifest.get("executionType") == "native_windows"
        has_wasm = "wasmRunner" in manifest or manifest.get("executionType") == "wasm"

        if has_native:
            rel = get_target_entry(manifest, "windows", plugin_id)
            target_f = plugin_dir / rel
            if not target_f.is_file():
                print(f"[FAIL] Plugin {plugin_id} missing Windows binary: {rel}")
                all_valid = False
            else:
                print(f"[PASS] Plugin {plugin_id} Windows binary verified: {rel} ({target_f.stat().st_size} bytes)")

        if has_wasm:
            rel = get_target_entry(manifest, "wasm", plugin_id)
            target_f = plugin_dir / rel
            if not target_f.is_file():
                print(f"[FAIL] Plugin {plugin_id} missing WASI binary: {rel}")
                all_valid = False
            else:
                print(f"[PASS] Plugin {plugin_id} WASI binary verified: {rel} ({target_f.stat().st_size} bytes)")

    return all_valid


def main():
    parser = argparse.ArgumentParser(description="Multi-Toolbox Plugin Cross-Compilation Tool")
    parser.add_argument("--plugin", "-p", help="Target plugin ID to build (default: all source plugins)")
    parser.add_argument(
        "--target",
        "-t",
        choices=["windows", "wasm", "all"],
        default="all",
        help="Target platform architecture to compile (default: all)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print build steps without executing cargo")
    parser.add_argument("--validate-only", action="store_true", help="Validate binary presence without compiling")
    parser.add_argument("--plugins-dir", default=None, help="Custom path to plugins directory")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    plugins_dir = Path(args.plugins_dir) if args.plugins_dir else repo_root / "plugins"

    if args.validate_only:
        valid = validate_plugin_binaries(plugins_dir)
        sys.exit(0 if valid else 1)

    projects = find_cargo_projects(plugins_dir, target_plugin_id=args.plugin)
    if not projects:
        if args.plugin:
            print(f"[INFO] Plugin '{args.plugin}' does not contain Cargo.toml source project.")
        else:
            print(f"[INFO] No plugins with Cargo.toml sources found in {plugins_dir}.")
        sys.exit(0)

    print(f"[*] Found {len(projects)} plugins with source code: {[p['plugin_id'] for p in projects]}")

    targets_to_build = ["windows", "wasm"] if args.target == "all" else [args.target]

    success_count = 0
    fail_count = 0

    for project in projects:
        manifest = project["manifest"]
        for target in targets_to_build:
            # Check if this target is relevant for this plugin
            if target == "windows":
                is_supported = (
                    "nativeRunner" in manifest
                    or manifest.get("executionType") == "native_windows"
                    or "dual" in project["plugin_id"]
                    or not manifest
                )
            else:
                is_supported = (
                    "wasmRunner" in manifest
                    or manifest.get("executionType") == "wasm"
                    or "wasm" in project["plugin_id"]
                    or not manifest
                )

            if not is_supported and len(targets_to_build) > 1:
                continue

            ok = compile_cargo_project(project, target, dry_run=args.dry_run)
            if ok:
                success_count += 1
            else:
                fail_count += 1

    print(f"\n[*] Compilation summary: {success_count} succeeded, {fail_count} failed.")
    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
