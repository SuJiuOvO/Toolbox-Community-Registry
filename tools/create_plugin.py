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


def validate_plugin_id(plugin_id: str) -> bool:
    return bool(re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", plugin_id))


def create_quickjs_template(target_dir: str, plugin_id: str, name: str, category: str, desc: str):
    manifest = {
        "$schema": "../../schemas/manifest.schema.json",
        "id": plugin_id,
        "name": name,
        "version": "1.0.0",
        "category": category,
        "description": desc,
        "author": "Community Developer",
        "icon": {
            "type": "material",
            "name": "extension"
        },
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
                "allowedExtensions": ["txt", "json", "png", "jpg"]
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
            "entry": "entry.js",
            "params": {}
        }
    }

    entry_js = f"""/// <reference path="../../types/toolbox.d.ts" />

/**
 * {name} ({plugin_id})
 * 基于 Multi-Toolbox QuickJS 宿主沙箱引擎
 */

async function run(ctx) {{
  Toolbox.log('【{name}】开始执行任务...');
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
    message: '{name} 执行成功！',
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

    with open(os.path.join(target_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with open(os.path.join(target_dir, "entry.js"), "w", encoding="utf-8") as f:
        f.write(entry_js)

    with open(os.path.join(target_dir, "README.md"), "w", encoding="utf-8") as f:
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
        "icon": {
            "type": "material",
            "name": "memory"
        },
        "engineType": "wasm",
        "executionType": "wasm",
        "platforms": ["universal"],
        "wasmRunner": {
            "entry": f"bin/{plugin_id_snake}.wasm",
            "executionMode": "wasi_cli",
            "args": ["-i", "{input}", "-o", "{outputDir}"],
            "batchMode": True,
            "showTerminal": True
        },
        "inputs": [
            {
                "id": "sourceFiles",
                "label": "选择待处理文件 (支持批量多选与整目录)",
                "type": "file_picker",
                "required": True,
                "allowMultiple": True
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

    main_rs = f"""// {name} ({plugin_id})
// Multi-Toolbox WASI 跨平台高性能算力微内核

use std::env;
use std::fs;
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
        let _ = fs::create_dir_all(out_dir);
    }}

    let dest_file = out_dir.join(format!("{{}}_processed.{{}}", file_stem, extension));

    match fs::read(&input_path) {{
        Ok(data) => {{
            println!(">>> 成功读取 {{}} 字节数据，正在执行核心算力算法...", data.len());
            // 在此处编写核心算法、多媒体解析或数据变换逻辑
            if let Err(e) = fs::write(&dest_file, &data) {{
                eprintln!("写入产物失败: {{}}", e);
                std::process::exit(1);
            }}
            println!("[+] 处理完成，产物已输出至: {{:?}}", dest_file);
        }}
        Err(e) => {{
            eprintln!("读取输入文件失败: {{}}", e);
            std::process::exit(1);
        }}
    }}
}}
"""

    build_bat = f"""@echo off
echo [1/2] 正在编译 Rust WASI 模块 (target: wasm32-wasip1)...
cargo build --target wasm32-wasip1 --release
if %ERRORLEVEL% neq 0 (
    echo 编译失败！请确保已安装 Rust 工具链并添加 WASI 目标：
    echo   rustup target add wasm32-wasip1
    exit /b %ERRORLEVEL%
)
if not exist bin mkdir bin
copy /Y "target\\wasm32-wasip1\\release\\{plugin_id_snake}.wasm" "bin\\{plugin_id_snake}.wasm"
echo [2/2] 编译完成！产物已复制至 bin\\{plugin_id_snake}.wasm
"""

    build_sh = f"""#!/bin/bash
set -e
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
   - Linux / macOS: 运行 `./build.sh`
3. 编译输出产物将自动放置于 `bin/{plugin_id_snake}.wasm`。

## 本地调试指南
1. 打开 Multi-Toolbox 客户端；
2. 进入「已安装插件 / 开发者工具」；
3. 点击「本地目录关联 (Dev Link)」，选择当前工程目录：`plugins/{plugin_id}`；
4. 运行工具，实时验证输入文件与产物输出。
"""

    os.makedirs(os.path.join(target_dir, "src"), exist_ok=True)
    os.makedirs(os.path.join(target_dir, "bin"), exist_ok=True)

    with open(os.path.join(target_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with open(os.path.join(target_dir, "Cargo.toml"), "w", encoding="utf-8") as f:
        f.write(cargo_toml)

    with open(os.path.join(target_dir, "src", "main.rs"), "w", encoding="utf-8") as f:
        f.write(main_rs)

    with open(os.path.join(target_dir, "build.bat"), "w", encoding="utf-8") as f:
        f.write(build_bat)

    with open(os.path.join(target_dir, "build.sh"), "w", encoding="utf-8") as f:
        f.write(build_sh)

    with open(os.path.join(target_dir, "bin", ".gitkeep"), "w", encoding="utf-8") as f:
        f.write("")

    with open(os.path.join(target_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme_md)


def create_win_ext_template(target_dir: str, plugin_id: str, name: str, category: str, desc: str):
    manifest = {
        "$schema": "../../schemas/manifest.schema.json",
        "id": plugin_id,
        "name": name,
        "version": "1.0.0",
        "minAppVersion": "1.0.0",
        "category": "win_ext" if category == "other" else category,
        "description": desc,
        "author": "Community Developer",
        "icon": {
            "type": "material",
            "name": "terminal"
        },
        "engineType": "win_native_runner",
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

    with open(os.path.join(target_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with open(os.path.join(target_dir, "bin", ".gitkeep"), "w", encoding="utf-8") as f:
        f.write("")

    with open(os.path.join(target_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme_md)


def main():
    parser = argparse.ArgumentParser(description="Multi-Toolbox 插件脚手架生成工具")
    parser.add_argument("--id", dest="plugin_id", help="插件唯一标识符 (全小写字母、数字与连字符，如 image-watermark-cleaner)")
    parser.add_argument("--name", dest="name", help="插件显示名称 (如 智能水印清除器)")
    parser.add_argument("--type", dest="engine_type", default="quickjs", choices=["quickjs", "wasm", "win_ext"], help="执行引擎类型 (默认: quickjs)")
    parser.add_argument("--category", dest="category", default="other", choices=["image", "media", "text", "crypto", "dev", "win_ext", "other"], help="插件分类")
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
        dev_hint = f"1. 运行 build.bat 或 ./build.sh 编译出 bin/{plugin_id.replace('-', '_')}.wasm；\n   2. 在客户端使用「本地目录关联」挂载此文件夹进行实时测试；\n   3. 完成后运行 python tools/build_registry.py 打包发布。"
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
