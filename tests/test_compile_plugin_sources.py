#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add tools to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from compile_plugin_sources import (
    find_cargo_projects,
    get_target_entry,
    compile_cargo_project,
    validate_plugin_binaries,
)


class TestCompilePluginSources(unittest.TestCase):
    def setUp(self):
        self.repo_root = REPO_ROOT
        self.plugins_dir = self.repo_root / "plugins"

    def test_find_cargo_projects_finds_plugins(self):
        projects = find_cargo_projects(self.plugins_dir)
        self.assertIsInstance(projects, list)
        plugin_ids = [p["plugin_id"] for p in projects]
        self.assertIn("image-pixel-richtext", plugin_ids)

    def test_find_cargo_projects_supports_filter(self):
        projects = find_cargo_projects(self.plugins_dir, target_plugin_id="image-pixel-richtext")
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["plugin_id"], "image-pixel-richtext")

        empty = find_cargo_projects(self.plugins_dir, target_plugin_id="non-existent-plugin-id")
        self.assertEqual(len(empty), 0)

    def test_get_target_entry_resolution(self):
        # Native runner specified
        manifest_win = {
            "nativeRunner": {"entry": "bin/custom.exe"}
        }
        self.assertEqual(get_target_entry(manifest_win, "windows", "my-plugin"), "bin/custom.exe")

        # Default fallback
        self.assertEqual(get_target_entry({}, "windows", "my-plugin"), "bin/my-plugin.exe")

        # WASM runner specified
        manifest_wasm = {
            "wasmRunner": {"entry": "bin/custom.wasm"}
        }
        self.assertEqual(get_target_entry(manifest_wasm, "wasm", "my-plugin"), "bin/custom.wasm")

        # Default WASM fallback
        self.assertEqual(get_target_entry({}, "wasm", "my-plugin"), "bin/my-plugin.wasm")

    def test_dry_run_compilation(self):
        project = {
            "plugin_id": "test-mock-plugin",
            "plugin_dir": Path("/tmp/mock-plugin"),
            "cargo_dir": Path("/tmp/mock-plugin/src"),
            "manifest": {
                "nativeRunner": {"entry": "bin/mock.exe"},
                "wasmRunner": {"entry": "bin/mock.wasm"},
            },
        }

        win_ok = compile_cargo_project(project, "windows", dry_run=True)
        self.assertTrue(win_ok)

        wasm_ok = compile_cargo_project(project, "wasm", dry_run=True)
        self.assertTrue(wasm_ok)

    def test_validate_plugin_binaries(self):
        valid = validate_plugin_binaries(self.plugins_dir)
        self.assertTrue(valid, "Existing source plugins should have compiled binaries in bin/")

    def test_cli_dry_run_and_validate_only_subprocesses(self):
        script_path = str(self.repo_root / "tools" / "compile_plugin_sources.py")

        # Test --dry-run
        res_dry = subprocess.run([sys.executable, script_path, "--dry-run"], capture_output=True, text=True)
        self.assertEqual(res_dry.returncode, 0, f"stdout: {res_dry.stdout}\nstderr: {res_dry.stderr}")
        self.assertIn("DRY-RUN", res_dry.stdout)

        # Test --validate-only
        res_val = subprocess.run([sys.executable, script_path, "--validate-only"], capture_output=True, text=True)
        self.assertEqual(res_val.returncode, 0, f"stdout: {res_val.stdout}\nstderr: {res_val.stderr}")
        self.assertIn("PASS", res_val.stdout)


if __name__ == "__main__":
    unittest.main()
