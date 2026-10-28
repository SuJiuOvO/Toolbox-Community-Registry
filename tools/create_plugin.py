#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Toolbox Plugin Scaffolding CLI Tool
一键创建包含标准 Manifest v2.4、TypeScript 类型感知与沙箱模板的插件工程
"""

import os
import sys
import json
import argparse
import re

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
  Toolbox.log('>>> 读取文件字节数:', fileContent.length);

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

## 🌟 功能特性
- 支持平台：Windows / Android（跨平台通用）
- 执行引擎：QuickJS 跨平台安全沙箱

## 🛠️ 本地调试指南
1. 打开 Multi-Toolbox 客户端；
2. 进入「已安装插件 / 开发者工具」；
3. 点击「本地目录关联 (Dev Link)」，选择当前工程目录：`plugins/{plugin_id}`；
4. 保存代码后即可在客户端内实时免重启热调试。
"""

    # 写入文件
    with open(os.path.join(target_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with open(os.path.join(target_dir, "entry.js"), "w", encoding="utf-8") as f:
        f.write(entry_js)

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
    else:
        # 默认基础生成
        create_quickjs_template(target_dir, plugin_id, name, args.category, args.desc)

    print("=" * 60)
    print(f"🎉 插件工程已成功初始化于: {target_dir}")
    print("📁 生成文件清单:")
    print(f"   - manifest.json  (已关联 schemas/manifest.schema.json 补全)")
    print(f"   - entry.js       (已预置 types/toolbox.d.ts TypeScript 感知)")
    print(f"   - README.md      (本地 Dev Link 调试与说明文档)")
    print("-" * 60)
    print("💡 立即开始开发:")
    print(f"   1. 使用 VS Code 打开 {target_dir}/entry.js，畅享智能提示与参数联想；")
    print(f"   2. 在客户端使用「本地目录关联」挂载此文件夹，保存即生效；")
    print(f"   3. 完成后运行 python tools/build_registry.py 即可验证打包。")
    print("=" * 60)


if __name__ == "__main__":
    main()
