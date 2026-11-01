import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

from tools import build_registry, create_plugin


ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = build_registry.load_validator(ROOT / "schemas" / "manifest.schema.json")


class RegistryToolsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "schemas").mkdir()
        shutil.copyfile(ROOT / "schemas" / "manifest.schema.json", self.root / "schemas" / "manifest.schema.json")
        (self.root / "plugins").mkdir()

    def scaffold(self, engine="quickjs", plugin_id="example-tool", category="other", name="示例工具"):
        argv = ["create_plugin.py", "--id", plugin_id, "--name", name, "--type", engine, "--category", category]
        with mock.patch.object(create_plugin, "PLUGINS_DIR", str(self.root / "plugins")), mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
            create_plugin.main()
        path = self.root / "plugins" / plugin_id
        return path, json.loads((path / "manifest.json").read_text(encoding="utf-8"))

    def prepare_index(self):
        path = self.root / "registry" / "index.json"
        path.parent.mkdir()
        path.write_text('{"version":"1.0.0","plugins":[]}', encoding="utf-8")
        return path

    def test_every_cli_type_and_category_passes_schema(self):
        for engine in ("quickjs", "wasm", "win_ext", "native_executable"):
            for category in create_plugin.CATEGORIES:
                with self.subTest(engine=engine, category=category):
                    plugin_id = f"example-{engine.replace('_', '-')}-{category.replace('_', '-')}"
                    path, manifest = self.scaffold(engine, plugin_id, category)
                    build_registry.validate_manifest(manifest, path, VALIDATOR)
                    self.assertIn("currentColor", manifest["icon"]["data"])
                    if engine in ("win_ext", "native_executable"):
                        self.assertEqual(manifest["executionType"], "native_executable")
                        self.assertEqual(manifest["platforms"], ["windows"])
                        self.assertNotIn("engineType", manifest)
                    elif engine == "wasm":
                        self.assertEqual(manifest["wasmRunner"]["args"][0], plugin_id.replace("-", "_"))
                        self.assertEqual(manifest["wasmRunner"]["executionMode"], "wasi_cli")
                        self.assertNotIn(b"\r\n", (path / "build.sh").read_bytes())
                    else:
                        self.assertEqual(manifest["action"]["handler"], "quickjs_eval")
                        self.assertTrue((path / "entry.js").is_file())
                        self.assertNotIn("entry", manifest["action"])

    def test_cli_rejects_invalid_ids_names_and_duplicate_directory(self):
        for plugin_id, engine, name in (("Bad_Id", "quickjs", "名称"), ("123-wasm", "wasm", "名称"), ("valid-id", "quickjs", "a"), ("valid-id", "quickjs", "a" * 61)):
            with self.subTest(plugin_id=plugin_id, engine=engine, name=name), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.scaffold(engine, plugin_id, name=name)
        self.assertEqual(list((self.root / "plugins").iterdir()), [])
        path, _ = self.scaffold()
        original = (path / "manifest.json").read_bytes()
        with self.assertRaises(SystemExit):
            self.scaffold()
        self.assertEqual((path / "manifest.json").read_bytes(), original)

    def test_schema_rejects_ignored_fields_and_invalid_nested_values(self):
        path, manifest = self.scaffold()
        invalid_fields = [
            ("icon", {"type": "material", "name": "memory"}),
            ("action", {"handler": "quickjs_eval", "entry": "entry.js"}),
            ("wasmRunner", {"entry": "bin/test.wasm", "executionMode": "direct_call"}),
            ("inputs", [{"id": "field", "label": "Field", "type": "unknown"}]),
            ("permissions", ["filesystem_unrestricted"]),
            ("version", "1.2.3invalid"),
        ]
        for key, value in invalid_fields:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "failed manifest schema"):
                build_registry.validate_manifest(dict(manifest, **{key: value}), path, VALIDATOR)

    def test_quickjs_source_lookup_matches_client(self):
        path, manifest = self.scaffold()
        (path / "entry.js").unlink()
        with self.assertRaisesRegex(ValueError, "no QuickJS source"):
            build_registry.validate_manifest(manifest, path, VALIDATOR)
        for filename in build_registry.QUICKJS_ENTRIES:
            entry = path / filename
            entry.write_text("async function run() {}", encoding="utf-8")
            build_registry.validate_manifest(manifest, path, VALIDATOR)
            entry.unlink()
        manifest["action"]["params"]["script"] = "async function run() {}"
        build_registry.validate_manifest(manifest, path, VALIDATOR)
        manifest["action"]["params"]["scriptFile"] = "analyzer.js"
        with self.assertRaisesRegex(ValueError, "scriptFile is ignored"):
            build_registry.validate_manifest(manifest, path, VALIDATOR)

    def test_all_existing_plugins_validate(self):
        manifests = list((ROOT / "plugins").glob("*/manifest.json"))
        self.assertGreaterEqual(len(manifests), 17)
        for path in manifests:
            with self.subTest(plugin=path.parent.name):
                build_registry.validate_manifest(json.loads(path.read_text(encoding="utf-8")), path.parent, VALIDATOR)

    def test_invalid_later_manifest_leaves_all_outputs_untouched(self):
        self.scaffold(plugin_id="a-valid")
        path, manifest = self.scaffold(plugin_id="z-invalid")
        manifest["inputs"][0]["type"] = "not-supported"
        (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        index = self.prepare_index()
        original = index.read_bytes()
        with self.assertRaisesRegex(ValueError, "z-invalid"):
            build_registry.build_registry(self.root)
        self.assertEqual(index.read_bytes(), original)
        self.assertFalse((self.root / "packages").exists())

    def test_packaging_error_leaves_all_outputs_untouched(self):
        self.scaffold(plugin_id="a-valid")
        self.scaffold(plugin_id="b-valid")
        index = self.prepare_index()
        original = index.read_bytes()
        with mock.patch.object(build_registry, "package_plugin", side_effect=[b"first", OSError("unreadable file")]), self.assertRaises(OSError):
            build_registry.build_registry(self.root)
        self.assertEqual(index.read_bytes(), original)
        self.assertFalse((self.root / "packages").exists())

    def test_validate_only_creates_no_outputs(self):
        self.scaffold()
        self.assertEqual(build_registry.build_registry(self.root, validate_only=True), 1)
        self.assertFalse((self.root / "packages").exists())
        self.assertFalse((self.root / "registry").exists())

    def test_packaging_is_deterministic_and_preserves_binary_bytes(self):
        path, _ = self.scaffold()
        for name in ("zdir", "adir", "target", ".cache"):
            (path / name).mkdir()
            (path / name / "data.bin").write_bytes(b"binary\r\n\x00")
        (path / ".secret").write_bytes(b"excluded")
        (path / ".gitkeep").write_bytes(b"")
        source = path / "entry.js"
        original = source.read_bytes()
        batch_file = path / "build.bat"
        batch_file.write_bytes(b"@echo off\n")
        first = build_registry.package_plugin(path)
        source.write_bytes(original.replace(b"\n", b"\r\n"))
        batch_file.write_bytes(b"@echo off\r\n")
        self.assertEqual(first, build_registry.package_plugin(path))
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            self.assertEqual(archive.read("adir/data.bin"), b"binary\r\n\x00")
            names = archive.namelist()
            self.assertLess(names.index("adir/data.bin"), names.index("zdir/data.bin"))
            self.assertNotIn("README.md", names)
            self.assertNotIn("target/data.bin", names)
            self.assertNotIn(".cache/data.bin", names)
            self.assertNotIn(".secret", names)
            self.assertIn(".gitkeep", names)
            for info in archive.infolist():
                self.assertEqual(info.create_system, 3)
                self.assertEqual(info.date_time, (2026, 1, 1, 0, 0, 0))

    def test_build_preserves_index_metadata_and_avoids_rewrites(self):
        self.scaffold()
        index = self.prepare_index()
        self.assertEqual(build_registry.build_registry(self.root), 1)
        result = json.loads(index.read_text(encoding="utf-8"))
        self.assertEqual(result["version"], "1.0.0")
        self.assertEqual(result["plugins"][0]["id"], "example-tool")
        with mock.patch.object(Path, "write_bytes", side_effect=AssertionError("unchanged output rewritten")):
            self.assertEqual(build_registry.build_registry(self.root), 1)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for the JavaScript runtime smoke test")
    def test_generated_javascript_runs_with_host_context(self):
        path, _ = self.scaffold(name="引号'\"与注释*/\n工具")
        script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const sandbox = {Toolbox: {log() {}, setProgress() {}, platform: 'windows', fs: {readText(path) {assert.equal(path, 'sample.txt'); return '你好 toolbox';}}}};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), sandbox);
(async () => {
  const result = await sandbox.run({inputFiles: ['sample.txt'], outputDir: '/output', params: {paramMode: 'enhanced'}});
  assert.equal(result.success, true);
  assert.match(result.data.summary, /enhanced/);
  const empty = await sandbox.run({inputFiles: [], params: {}});
  assert.equal(empty.success, false);
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
        result = subprocess.run([shutil.which("node"), "-e", script, str(path / "entry.js")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(os.environ.get("TOOLBOX_TEST_WASI") == "1", "Set TOOLBOX_TEST_WASI=1 with Rust wasm32-wasip1 and Node.js installed")
    def test_rust_template_builds_and_runs_manifest_arguments(self):
        path, manifest = self.scaffold("wasm", "wasi-smoke", name="引号'\"与注释*/\n工具")
        command = ["cmd", "/c", str(path / "build.bat")] if os.name == "nt" else ["bash", str(path / "build.sh")]
        # Build from outside the project to exercise the scripts' directory handling.
        build = subprocess.run(command, cwd=self.root, capture_output=True, timeout=180)
        self.assertEqual(build.returncode, 0, build.stderr.decode("utf-8", errors="replace"))
        self.assertTrue((path / manifest["wasmRunner"]["entry"]).is_file())
        (path / "sample.txt").write_bytes(("多字节 UTF-8 与流式输出\n" * 100000).encode("utf-8"))
        (path / "output").mkdir()
        script = r"""
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {WASI} = require('node:wasi');
const root = process.argv[1];
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifest.json'), 'utf8'));
(async () => {
  const module = await WebAssembly.compile(fs.readFileSync(path.join(root, manifest.wasmRunner.entry)));
  for (const input of ['/work/sample.txt', '/work/missing.txt']) {
    const args = manifest.wasmRunner.args.map(arg => arg.replace('{input}', input).replace('{outputDir}', '/work/output'));
    const wasi = new WASI({version: 'preview1', args, preopens: {'/work': root}, returnOnExit: true});
    const instance = await WebAssembly.instantiate(module, {wasi_snapshot_preview1: wasi.wasiImport});
    const code = wasi.start(instance);
    assert.equal(code, input.endsWith('sample.txt') ? 0 : 1);
  }
  assert.deepEqual(fs.readFileSync(path.join(root, 'sample.txt')), fs.readFileSync(path.join(root, 'output/sample_processed.txt')));
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
        run = subprocess.run([shutil.which("node"), "-e", script, str(path)], capture_output=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8", errors="replace"))


if __name__ == "__main__":
    unittest.main()
