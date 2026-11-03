#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Toolbox Plugin Scaffolding CLI Tool
一键创建包含标准 Manifest v2.5、TypeScript 类型感知或 Rust WASI / Windows Native 模板的插件工程
"""

import os
import sys
import json
import argparse
import re

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGINS_DIR = os.path.join(BASE_DIR, "plugins")
CATEGORIES = ("image", "media", "text", "dev", "system", "audio", "video", "archive", "document", "network", "utility", "other", "win_ext")


def template_icon(path: str) -> dict:
    return {
        "type": "code",
        "data": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<rect x="3" y="3" width="18" height="18" rx="5" fill="currentColor" fill-opacity="0.22"/>'
        f'<path d="{path}" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>',
    }


def validate_plugin_id(plugin_id: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", plugin_id))


def create_quickjs_template(target_dir: str, plugin_id: str, name: str, category: str, desc: str):
    manifest = {
        "$schema": "../../schemas/manifest.schema.json",
        "id": plugin_id,
        "name": name,
        "version": "1.0.0",
        "category": category,
        "description": desc,
        "author": "Community Developer",
        "icon": template_icon("M9 8l-4 4 4 4m6-8 4 4-4 4m-2-9-2 14"),
        "engineType": "quickjs",
        "executionType": "quickjs",
        "platforms": ["universal"],
        "permissions": [],
        "inputs": [
            {
                "id": "sourceFile",
                "label": "选择输入文件",
                "type": "file_picker",
                "required": True,
                "allowMultiple": False,
                "allowedExtensions": ["txt", "json"]
            },
            {
                "id": "paramMode",
                "label": "处理模式",
                "type": "select",
                "defaultValue": "default",
                "options": [
                    {"label": "默认极速模式", "value": "default"},
                    {"label": "高级增强模式", "value": "enhanced"}
                ]
            }
        ],
        "outputs": [
            {
                "id": "summary",
                "label": "执行结果摘要",
                "type": "copyable_text"
            }
        ],
        "action": {
            "handler": "quickjs_eval",
            "params": {}
        }
    }

    entry_js = f"""/// <reference path="../../types/toolbox.d.ts" />

/**
 * Plugin: {plugin_id}
 * 基于 Multi-Toolbox QuickJS 宿主沙箱引擎
 */

async function run(ctx) {{
  Toolbox.log('开始执行任务...');
  Toolbox.log('>>> 当前宿主平台:', Toolbox.platform);
  Toolbox.log('>>> 输入文件列表:', ctx.inputFiles);
  Toolbox.log('>>> 表单参数映射:', ctx.params);

  Toolbox.setProgress(0.3, '正在读取并解析输入数据...');
  
  if (!ctx.inputFiles || ctx.inputFiles.length === 0) {{
    return {{
      success: false,
      message: '请至少选择一个输入文件'
    }};
  }}

  const inputFile = ctx.inputFiles[0];
  const fileContent = Toolbox.fs.readText(inputFile);
  Toolbox.log('>>> 读取文件字符数:', fileContent.length);

  Toolbox.setProgress(0.7, '正在处理业务逻辑...');
  // 在此处编写核心计算逻辑...

  Toolbox.setProgress(1.0, '处理完毕');
  return {{
    success: true,
    message: '插件执行成功！',
    text: `已成功处理文件: ${{inputFile}}\\n大小: ${{fileContent.length}} 字符`,
    data: {{
      summary: `文件处理完毕，当前模式: ${{ctx.params.paramMode || 'default'}}`
    }}
  }};
}}
"""

    readme_md = f"""# {name} (`{plugin_id}`)

{desc}

## 功能特性
- 支持平台：Windows / Android（跨平台通用）
- 执行引擎：QuickJS 跨平台安全沙箱

## 本地调试指南
1. 打开 Multi-Toolbox 客户端；
2. 进入「已安装插件 / 开发者工具」；
3. 点击「本地目录关联 (Dev Link)」，选择当前工程目录：`plugins/{plugin_id}`；
4. 保存代码后即可在客户端内实时免重启热调试。
"""

    with open(os.path.join(target_dir, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with open(os.path.join(target_dir, "entry.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write(entry_js)

    with open(os.path.join(target_dir, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(readme_md)


def create_wasm_rust_template(target_dir: str, plugin_id: str, name: str, category: str, desc: str):
    plugin_id_snake = plugin_id.replace("-", "_")

    manifest = {
        "$schema": "../../schemas/manifest.schema.json",
        "id": plugin_id,
        "name": name,
        "version": "1.0.0",
        "minAppVersion": "1.0.0",
        "category": category,
        "description": desc,
        "author": "Community Developer",
        "icon": template_icon("M8 8h8v8H8zM9 3v2m6-2v2M9 19v2m6-2v2M3 9h2m-2 6h2M19 9h2m-2 6h2"),
        "engineType": "wasm",
        "executionType": "wasm",
        "platforms": ["universal"],
        "wasmRunner": {
            "entry": f"bin/{plugin_id_snake}.wasm",
            "executionMode": "wasi_cli",
            "args": [plugin_id_snake, "-i", "{input}", "-o", "{outputDir}"],
            "batchMode": True,
            "showTerminal": True
        },
        "inputs": [
            {
                "id": "sourceFiles",
                "label": "选择待处理文件 (支持批量多选与整目录)",
                "type": "file_picker",
                "required": True,
                "allowMultiple": True,
                "allowFolder": True
            }
        ],
        "action": {
            "handler": "wasm_universal",
            "params": {}
        }
    }

    cargo_toml = f"""[package]
name = "{plugin_id_snake}"
version = "0.1.0"
edition = "2021"

[dependencies]
"""

    main_rs = f"""// Plugin: {plugin_id}
// Multi-Toolbox WASI 跨平台高性能算力微内核

use std::env;
use std::fs;
use std::io;
use std::path::Path;

fn main() {{
    println!("=== Multi-Toolbox WASI 算力内核已启动 ===");
    let args: Vec<String> = env::args().collect();
    let mut input_path = String::new();
    let mut output_dir = String::new();

    let mut i = 1;
    while i < args.len() {{
        match args[i].as_str() {{
            "-i" | "--input" => {{
                if i + 1 < args.len() {{
                    input_path = args[i + 1].clone();
                    i += 1;
                }}
            }}
            "-o" | "--output" => {{
                if i + 1 < args.len() {{
                    output_dir = args[i + 1].clone();
                    i += 1;
                }}
            }}
            "-h" | "--help" => {{
                println!("用法: {{}} -i <输入文件路径> -o <输出目录>", args[0]);
                return;
            }}
            _ => {{}}
        }}
        i += 1;
    }}

    if input_path.is_empty() || output_dir.is_empty() {{
        eprintln!("错误: 缺少必要参数 -i <input> 或 -o <output>");
        std::process::exit(1);
    }}

    println!(">>> 输入文件: {{}}", input_path);
    println!(">>> 输出目录: {{}}", output_dir);

    let in_path = Path::new(&input_path);
    let file_stem = in_path.file_stem().and_then(|s| s.to_str()).unwrap_or("output");
    let extension = in_path.extension().and_then(|s| s.to_str()).unwrap_or("dat");

    let out_dir = Path::new(&output_dir);
    if !out_dir.exists() {{
        if let Err(e) = fs::create_dir_all(out_dir) {{
            eprintln!("创建输出目录失败: {{}}", e);
            std::process::exit(1);
        }}
    }}

    let dest_file = out_dir.join(format!("{{}}_processed.{{}}", file_stem, extension));

    // io::copy 使用固定大小的缓冲区，避免将整个大文件读入内存。
    // 可在此处将流式复制替换为自己的转换算法。
    let result = (|| -> io::Result<u64> {{
        let mut source = fs::File::open(in_path)?;
        let mut destination = fs::File::create(&dest_file)?;
        io::copy(&mut source, &mut destination)
    }})();
    match result {{
        Ok(byte_count) => {{
            println!(">>> 已流式处理 {{}} 字节数据", byte_count);
            println!("[+] 处理完成，产物已输出至: {{:?}}", dest_file);
        }}
        Err(e) => {{
            eprintln!("处理输入文件失败: {{}}", e);
            std::process::exit(1);
        }}
    }}
}}
"""

    build_bat = f"""@echo off
setlocal
pushd "%~dp0"
echo [1/2] 正在编译 Rust WASI 模块 (target: wasm32-wasip1)...
cargo build --target wasm32-wasip1 --release
if %ERRORLEVEL% neq 0 (
    echo 编译失败！请确保已安装 Rust 工具链并添加 WASI 目标：
    echo   rustup target add wasm32-wasip1
    popd
    exit /b 1
)
if not exist bin mkdir bin
copy /Y "target\\wasm32-wasip1\\release\\{plugin_id_snake}.wasm" "bin\\{plugin_id_snake}.wasm"
if errorlevel 1 (
    popd
    exit /b 1
)
echo [2/2] 编译完成！产物已复制至 bin\\{plugin_id_snake}.wasm
popd
"""

    build_sh = f"""#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
echo "[1/2] 正在编译 Rust WASI 模块 (target: wasm32-wasip1)..."
cargo build --target wasm32-wasip1 --release
mkdir -p bin
cp "target/wasm32-wasip1/release/{plugin_id_snake}.wasm" "bin/{plugin_id_snake}.wasm"
echo "[2/2] 编译完成！产物已复制至 bin/{plugin_id_snake}.wasm"
"""

    readme_md = f"""# {name} (`{plugin_id}`)

{desc}

## 功能特性
- 支持平台：Windows / Android（跨平台通用）
- 执行引擎：WASI Preview 1 内存沙箱微内核 (Rust / C / C++)

## 构建指南 (Rust WASI)
1. 确保已安装 Rust 并添加 `wasm32-wasip1` 编译目标：
   ```bash
   rustup target add wasm32-wasip1
   ```
2. 执行一键构建脚本生成 `.wasm` 产物：
   - Windows: 运行 `build.bat`
   - Linux / macOS: 运行 `bash build.sh`
3. 编译输出产物将自动放置于 `bin/{plugin_id_snake}.wasm`。

## 本地调试指南
1. 打开 Multi-Toolbox 客户端；
2. 进入「已安装插件 / 开发者工具」；
3. 点击「本地目录关联 (Dev Link)」，选择当前工程目录：`plugins/{plugin_id}`；
4. 运行工具，实时验证输入文件与产物输出。
"""

    os.makedirs(os.path.join(target_dir, "src"), exist_ok=True)
    os.makedirs(os.path.join(target_dir, "bin"), exist_ok=True)

    with open(os.path.join(target_dir, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with open(os.path.join(target_dir, "Cargo.toml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(cargo_toml)

    with open(os.path.join(target_dir, "src", "main.rs"), "w", encoding="utf-8", newline="\n") as f:
        f.write(main_rs)

    with open(os.path.join(target_dir, "build.bat"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(build_bat)

    with open(os.path.join(target_dir, "build.sh"), "w", encoding="utf-8", newline="\n") as f:
        f.write(build_sh)

    with open(os.path.join(target_dir, "bin", ".gitkeep"), "w", encoding="utf-8") as f:
        f.write("")

    with open(os.path.join(target_dir, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(readme_md)


def create_win_ext_template(target_dir: str, plugin_id: str, name: str, category: str, desc: str):
    manifest = {
        "$schema": "../../schemas/manifest.schema.json",
        "id": plugin_id,
        "name": name,
        "version": "1.0.0",
        "minAppVersion": "1.0.0",
        "category": "system" if category == "other" else category,
        "description": desc,
        "author": "Community Developer",
        "icon": template_icon("M7 8l4 4-4 4m6 0h4"),
        "executionType": "native_executable",
        "platforms": ["windows"],
        "nativeRunner": {
            "entry": f"bin/{plugin_id}.exe",
            "args": ["-o", "{outputDir}", "{inputs}"],
            "showTerminal": True
        },
        "inputs": [
            {
                "id": "sourceFiles",
                "label": "选择待处理文件 (支持批量)",
                "type": "file_picker",
                "required": True,
                "allowMultiple": True
            }
        ]
    }

    readme_md = f"""# {name} (`{plugin_id}`)

{desc}

## 功能特性
- 支持平台：Windows（开放工坊）
- 执行引擎：Windows 原生可执行文件 (`native_executable`)

## 配置与使用说明
1. 将你的 Windows 原生命令行工具放置于 `bin/{plugin_id}.exe`（或在 `manifest.json` 中配置为系统 PATH 中已有的命令，如 `curl.exe`、`ffmpeg.exe`）；
2. 参数占位符说明：
   - `{{inputs}}`: 用户选择的全部输入文件绝对路径（以空格分隔）；
   - `{{input}}`: 首个输入文件绝对路径；
   - `{{outputDir}}`: 宿主分配的专属输出目录绝对路径；
   - `{{form_field_id}}`: 动态表单项中对应 id 的填写值；
3. 本地调试：
   - 打开 Multi-Toolbox 客户端；
   - 使用「本地目录关联 (Dev Link)」挂载本目录 `plugins/{plugin_id}` 即可直接运行调试。
"""

    os.makedirs(os.path.join(target_dir, "bin"), exist_ok=True)

    with open(os.path.join(target_dir, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with open(os.path.join(target_dir, "bin", ".gitkeep"), "w", encoding="utf-8") as f:
        f.write("")

    with open(os.path.join(target_dir, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(readme_md)


def create_dual_adaptive_template(target_dir: str, plugin_id: str, name: str, category: str, desc: str):
    plugin_id_snake = plugin_id.replace("-", "_")

    manifest = {
        "$schema": "../../schemas/manifest.schema.json",
        "id": plugin_id,
        "name": name,
        "version": "1.0.0",
        "minAppVersion": "1.0.0",
        "category": category,
        "description": desc,
        "author": "Community Developer",
        "icon": template_icon("M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"),
        "executionType": "wasm",
        "platforms": ["windows", "android"],
        "nativeRunner": {
            "entry": f"bin/{plugin_id}.exe",
            "args": ["-o", "{outputDir}", "{inputs}"],
            "showTerminal": True
        },
        "wasmRunner": {
            "entry": f"bin/{plugin_id_snake}.wasm",
            "executionMode": "wasi_cli",
            "args": [plugin_id_snake, "-i", "{input}", "-o", "{outputDir}"],
            "batchMode": True,
            "showTerminal": True
        },
        "inputs": [
            {
                "id": "sourceFiles",
                "label": "选择待处理文件 (支持批量多选与整目录)",
                "type": "file_picker",
                "required": True,
                "allowMultiple": True,
                "allowFolder": True
            }
        ],
        "action": {
            "handler": "wasm_universal",
            "params": {}
        }
    }

    cargo_toml = f"""[package]
name = "{plugin_id_snake}"
version = "0.1.0"
edition = "2021"

[dependencies]
"""

    main_rs = f"""// Plugin: {plugin_id}
// Multi-Toolbox 双端自适应合一算力微内核 (Windows 原生 EXE + Android WASI 沙箱)

use std::env;
use std::fs;
use std::io;
use std::path::Path;

fn main() {{
    println!("=== Multi-Toolbox 双端自适应算力内核已启动 ===");
    let args: Vec<String> = env::args().collect();
    let mut input_paths: Vec<String> = Vec::new();
    let mut output_dir = String::new();

    let mut i = 1;
    while i < args.len() {{
        match args[i].as_str() {{
            "-i" | "--input" => {{
                if i + 1 < args.len() {{
                    input_paths.push(args[i + 1].clone());
                    i += 1;
                }}
            }}
            "-o" | "--output" => {{
                if i + 1 < args.len() {{
                    output_dir = args[i + 1].clone();
                    i += 1;
                }}
            }}
            other => {{
                if !other.starts_with('-') {{
                    input_paths.push(other.to_string());
                }}
            }}
        }}
        i += 1;
    }}

    if input_paths.is_empty() || output_dir.is_empty() {{
        eprintln!("用法错误: 缺少必要参数！");
        eprintln!("  双端自适应 CLI 规范:");
        eprintln!("    单文件/WASI 模式: {plugin_id_snake} -i <输入文件> -o <输出目录>");
        eprintln!("    多文件/原生 模式: {plugin_id_snake} -o <输出目录> <文件1> [文件2 ...]");
        std::process::exit(1);
    }}

    let out_dir = Path::new(&output_dir);
    if !out_dir.exists() {{
        if let Err(e) = fs::create_dir_all(out_dir) {{
            eprintln!("创建输出目录失败: {{}}", e);
            std::process::exit(1);
        }}
    }}

    println!(">>> 待处理输入文件数量: {{}}", input_paths.len());
    println!(">>> 目标输出目录: {{:?}}", out_dir);

    for in_str in &input_paths {{
        let in_path = Path::new(in_str);
        if !in_path.exists() {{
            eprintln!("输入文件不存在: {{}}", in_str);
            std::process::exit(1);
        }}

        let file_stem = in_path.file_stem().and_then(|s| s.to_str()).unwrap_or("output");
        let extension = in_path.extension().and_then(|s| s.to_str()).unwrap_or("txt");
        let dest_file = out_dir.join(format!("{{}}_processed.{{}}", file_stem, extension));

        let result = (|| -> io::Result<u64> {{
            let mut source = fs::File::open(in_path)?;
            let mut destination = fs::File::create(&dest_file)?;
            io::copy(&mut source, &mut destination)
        }})();

        match result {{
            Ok(byte_count) => {{
                println!(">>> 已处理: {{:?}} ({{}} 字节) -> {{:?}}", in_path, byte_count, dest_file);
            }}
            Err(e) => {{
                eprintln!("处理文件失败 ({{:?}}): {{}}", in_path, e);
                std::process::exit(1);
            }}
        }}
    }}

    println!("[+] 全部文件处理完成！");
}}
"""

    build_win_bat = f"""@echo off
setlocal
pushd "%~dp0"
echo [1/2] 正在编译 Windows 原生可执行文件 (target: native release)...
cargo build --release
if %ERRORLEVEL% neq 0 (
    echo Windows 原生编译失败！请确保已安装 Rust 工具链。
    popd
    exit /b 1
)
if not exist bin mkdir bin
copy /Y "target\\release\\{plugin_id_snake}.exe" "bin\\{plugin_id}.exe"
if errorlevel 1 (
    popd
    exit /b 1
)
echo [2/2] 编译完成！产物已复制至 bin\\{plugin_id}.exe
popd
"""

    build_wasm_bat = f"""@echo off
setlocal
pushd "%~dp0"
echo [1/2] 正在编译 Rust WASI 模块 (target: wasm32-wasip1)...
cargo build --target wasm32-wasip1 --release
if %ERRORLEVEL% neq 0 (
    echo WASI 编译失败！请确保已安装 Rust 工具链并添加 WASI 目标：
    echo   rustup target add wasm32-wasip1
    popd
    exit /b 1
)
if not exist bin mkdir bin
copy /Y "target\\wasm32-wasip1\\release\\{plugin_id_snake}.wasm" "bin\\{plugin_id_snake}.wasm"
if errorlevel 1 (
    popd
    exit /b 1
)
echo [2/2] 编译完成！产物已复制至 bin\\{plugin_id_snake}.wasm
popd
"""

    build_bat = f"""@echo off
setlocal
pushd "%~dp0"
echo ========================================================
echo   Multi-Toolbox 双端自适应插件一键构建流水线
echo   1. Windows 原生二进制: bin\\{plugin_id}.exe
echo   2. Android / 通用 WASI 模块: bin\\{plugin_id_snake}.wasm
echo ========================================================
call "%~dp0build_win.bat"
if %ERRORLEVEL% neq 0 (
    echo [警告] Windows 原生构建遇到错误。
)
call "%~dp0build_wasm.bat"
if %ERRORLEVEL% neq 0 (
    echo [警告] WASI 构建遇到错误。
)
popd
"""

    build_sh = f"""#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
echo "[1/2] 正在编译 Rust WASI 模块 (target: wasm32-wasip1)..."
cargo build --target wasm32-wasip1 --release
mkdir -p bin
cp "target/wasm32-wasip1/release/{plugin_id_snake}.wasm" "bin/{plugin_id_snake}.wasm"
echo "[2/2] 编译完成！产物已复制至 bin/{plugin_id_snake}.wasm"
"""

    readme_md = f"""# {name} (`{plugin_id}`)

{desc}

## 功能特性
- 支持平台：Windows / Android（🚀 双端自适应合一架构）
- 执行引擎：
  - Windows 端：自动调度本地原生极速程序 `bin/{plugin_id}.exe`（裸机性能，极速秒出）；
  - Android 端：无缝切换至 `bin/{plugin_id_snake}.wasm`（WASI Preview 1 内存沙箱微内核）。

## 构建指南 (Rust 双端编译)
1. 准备环境：确保已安装 Rust 工具链并添加 `wasm32-wasip1` 编译目标：
   ```bash
   rustup target add wasm32-wasip1
   ```
2. 构建产物：
   - **一键双端编译 (Windows)**：运行 `build.bat`，自动在 `bin/` 目录下生成 `.exe` 和 `.wasm`；
   - **仅编译 Windows 原生**：运行 `build_win.bat`；
   - **仅编译 Android WASI**：运行 `build_wasm.bat`（或 Linux/macOS 执行 `bash build.sh`）。

## 本地调试指南
1. 打开 Multi-Toolbox 客户端；
2. 进入「已安装插件 / 开发者工具」；
3. 点击「本地目录关联 (Dev Link)」，挂载当前工程目录：`plugins/{plugin_id}`；
4. Windows 端将直接以原生机器码调度，Android 端将自动以 WASI 隔离沙箱调度，即刻实时验证。
"""

    os.makedirs(os.path.join(target_dir, "src"), exist_ok=True)
    os.makedirs(os.path.join(target_dir, "bin"), exist_ok=True)

    with open(os.path.join(target_dir, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with open(os.path.join(target_dir, "Cargo.toml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(cargo_toml)

    with open(os.path.join(target_dir, "src", "main.rs"), "w", encoding="utf-8", newline="\n") as f:
        f.write(main_rs)

    with open(os.path.join(target_dir, "build_win.bat"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(build_win_bat)

    with open(os.path.join(target_dir, "build_wasm.bat"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(build_wasm_bat)

    with open(os.path.join(target_dir, "build.bat"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(build_bat)

    with open(os.path.join(target_dir, "build.sh"), "w", encoding="utf-8", newline="\n") as f:
        f.write(build_sh)

    with open(os.path.join(target_dir, "bin", ".gitkeep"), "w", encoding="utf-8") as f:
        f.write("")

    with open(os.path.join(target_dir, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(readme_md)


def main():
    parser = argparse.ArgumentParser(description="Multi-Toolbox 插件脚手架生成工具")
    parser.add_argument("--id", dest="plugin_id", help="插件唯一标识符 (全小写字母、数字与连字符，如 image-watermark-cleaner)")
    parser.add_argument("--name", dest="name", help="插件显示名称 (如 智能水印清除器)")
    parser.add_argument("--type", dest="engine_type", default="quickjs", choices=["quickjs", "wasm", "win_ext", "native_executable", "dual", "dual_adaptive"], help="执行引擎类型 (默认: quickjs；dual/dual_adaptive 为双端自适应合一；native_executable 是 win_ext 的别名)")
    parser.add_argument("--category", dest="category", default="other", choices=CATEGORIES, help="插件分类")
    parser.add_argument("--desc", dest="desc", default="Multi-Toolbox 社区实用功能模块", help="插件功能描述")

    args = parser.parse_args()

    plugin_id = args.plugin_id
    if not plugin_id:
        if sys.stdin.isatty():
            plugin_id = input("请输入插件唯一 ID (如 my-awesome-tool): ").strip()
        else:
            print("错误: 必须提供 --id 参数")
            sys.exit(1)

    if not validate_plugin_id(plugin_id):
        print(f"错误: 插件 ID '{plugin_id}' 不符合规范，必须为纯小写英文字母、数字和短连字符组成 (如 my-tool-01)")
        sys.exit(1)

    name = args.name
    if not name:
        if sys.stdin.isatty():
            name = input("请输入插件显示名称 (如 我的实用工具): ").strip() or plugin_id
        else:
            name = plugin_id

    if not 2 <= len(name) <= 60:
        parser.error("插件显示名称必须为 2 到 60 个字符")

    # Rust crate 名称不能以数字开头，即使插件 ID 本身允许数字。
    if args.engine_type in ("wasm", "dual") and not plugin_id[0].isalpha():
        parser.error("WASM 插件 ID 必须以英文字母开头，以兼容 Rust crate 名称")

    if args.engine_type == "native_executable":
        args.engine_type = "win_ext"
    if args.engine_type == "dual_adaptive":
        args.engine_type = "dual"

    target_dir = os.path.join(PLUGINS_DIR, plugin_id)
    if os.path.exists(target_dir):
        print(f"错误: 目标插件目录已存在: {target_dir}")
        sys.exit(1)

    os.makedirs(target_dir, exist_ok=True)

    if args.engine_type == "quickjs":
        create_quickjs_template(target_dir, plugin_id, name, args.category, args.desc)
        file_list = [
            "manifest.json (已关联 schemas/manifest.schema.json 补全)",
            "entry.js      (已预置 types/toolbox.d.ts TypeScript 感知)",
            "README.md     (本地 Dev Link 调试与说明文档)"
        ]
        dev_hint = f"1. 使用 VS Code 打开 {target_dir}/entry.js，畅享智能提示与参数联想；\n   2. 在客户端使用「本地目录关联」挂载此文件夹，保存即生效；\n   3. 完成后运行 python tools/build_registry.py 即可验证打包。"
    elif args.engine_type == "wasm":
        create_wasm_rust_template(target_dir, plugin_id, name, args.category, args.desc)
        file_list = [
            "manifest.json (已配置 wasmRunner 与 wasi_cli CLI 模式)",
            "Cargo.toml    (标准 Rust WASI 编译工程文件)",
            "src/main.rs   (WASI VFS 缓冲流与命令行参数解析模板)",
            "build.bat     (Windows 一键 cargo build wasm32-wasip1 脚本)",
            "build.sh      (Linux/macOS 一键构建脚本)",
            "bin/          (WASM 输出目录)",
            "README.md     (Rust WASI 编译指引与 Dev Link 说明)"
        ]
        dev_hint = f"1. 运行 build.bat 或 bash build.sh 编译出 bin/{plugin_id.replace('-', '_')}.wasm；\n   2. 在客户端使用「本地目录关联」挂载此文件夹进行实时测试；\n   3. 完成后运行 python tools/build_registry.py 打包发布。"
    elif args.engine_type == "dual":
        create_dual_adaptive_template(target_dir, plugin_id, name, args.category, args.desc)
        file_list = [
            "manifest.json (已配置 nativeRunner 与 wasmRunner 双端自适应合一)",
            "Cargo.toml    (标准 Rust 双端编译工程文件)",
            "src/main.rs   (双端自适应 CLI 参数与流式文件处理模板)",
            "build.bat     (Windows 双端一键编译脚本)",
            "build_win.bat (仅编译 Windows 原生 .exe 脚本)",
            "build_wasm.bat(仅编译 Android WASI .wasm 脚本)",
            "build.sh      (Linux/macOS WASI 构建脚本)",
            "bin/          (双端二进制输出目录)",
            "README.md     (双端自适应架构与 Dev Link 调试说明)"
        ]
        dev_hint = f"1. 运行 build.bat (或分别运行 build_win.bat / build_wasm.bat) 生成二进制；\n   2. 在客户端使用「本地目录关联」挂载此文件夹：Windows 自动跑原生 EXE，Android 自动跑 WASI 沙箱；\n   3. 完成后运行 python tools/build_registry.py 打包发布。"
    elif args.engine_type == "win_ext":
        create_win_ext_template(target_dir, plugin_id, name, args.category, args.desc)
        file_list = [
            "manifest.json (已配置 nativeRunner 与 Windows 平台约束)",
            "bin/          (可执行文件存放目录)",
            "README.md     (Windows Native CLI 说明文档)"
        ]
        dev_hint = f"1. 将 Windows CLI 工具放入 {target_dir}/bin/；\n   2. 在客户端使用「本地目录关联」挂载此文件夹验证；\n   3. 完成后运行 python tools/build_registry.py 打包发布。"

    print("=" * 60)
    print(f"[+] 插件工程已成功初始化于: {target_dir} [{args.engine_type}]")
    print("生成文件清单:")
    for item in file_list:
        print(f"   - {item}")
    print("-" * 60)
    print("立即开始开发:")
    print(f"   {dev_hint}")
    print("=" * 60)


if __name__ == "__main__":
    main()
