# 🌐 Multi-Toolbox 社区功能模块注册中心 (Toolbox-Community-Registry)

<p align="center">
  <b>Multi-Toolbox (多功能动态百宝箱) 官方社区功能模块与动态插件生态仓库</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Manifest-v2.0-blue.svg" alt="Manifest v2.0" />
  <img src="https://img.shields.io/badge/Runtimes-Wasm%20%7C%20QuickJS%20%7C%20CLI-6366F1" alt="Runtimes" />
  <img src="https://img.shields.io/badge/Mirrors-Gitee%20%7C%20jsDelivr%20%7C%20GitHub-4CAF50" alt="Mirrors" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License" />
</p>

---

## 📖 仓库简介

**Toolbox-Community-Registry** 是 [Multi-Toolbox](https://github.com/SuJiuOvO/Multi-Toolbox) 的去中心化插件与功能模块托管中心。

客户端采用 **插件化微内核架构**，应用本体极其轻量（无预捆绑冗余），海量生产力工具均以声明式模块的形式在本仓库中维护与托管。用户在百宝箱客户端的「模块市场」中浏览、一键下载与热插拔安装的全部工具，均由本仓库通过自动化 CI 流程统一构建与分发。

无论您擅长 **JavaScript / TypeScript**、**C / C++ / Rust (WebAssembly)**，还是擅长 **Python / PowerShell / CLI 命令行工具开发**，都可以按照开发规范为百宝箱添加全新的实用工具，并通过提交 PR 共享给全球所有百宝箱用户！

---

## 🌟 模块运行时体系与支持范式

百宝箱底座支持 4 大隔离沙箱执行范式，开发者可按需选用：

| 运行时范式 | 核心技术栈 | 跨平台支持 | 适用场景 |
| :--- | :--- | :---: | :--- |
| **WebAssembly (Wasm) 算力沙箱** | C / C++ / Rust / Go | 🌐 Windows / Android 全兼容 | 密集数学计算、密码学、音视频编解码、高性能数据压缩/解压 |
| **QuickJS 跨平台脚本沙箱** | JavaScript (ES2020) | 🌐 Windows / Android 全兼容 | 文本处理、数据清洗、正则解析、格式转换、规则过滤 |
| **Windows 独立扩展工坊** | CLI 可执行程序、PowerShell、Python | 🪟 Windows 专享 | 挂接现成的大型命令行工具（如 ffmpeg, yt-dlp, 7z），带流式终端回显 |
| **客户端内置算法流水线** | 客户端底层图形/文档引擎 | 🌐 Windows / Android 全兼容 | 逆向 Alpha 混合数学无损去水印、图像等比缩放、PDF 矢量拆分合并 |

---

## 📚 开发者技术文档 (必读 🌟)

为方便所有开发者无障碍开发与接入功能模块，我们准备了详尽的全栈技术开发手册：

👉 **[《Multi-Toolbox 社区功能模块（插件）全栈开发与技术架构指南 (Manifest v2.0)》](docs/PLUGIN_DEVELOPMENT_GUIDE.md)**

### 手册核心内容速览：
- **四大执行模式开发指南**：手把手教您如何用 Rust 编译 `.wasm`、编写 QuickJS 脚本及配置 Windows CLI 扩展。
- **Manifest v2.0 清单规范完整参考**：
  - **最新图标系统规范**：支持 SVG 矢量代码直接渲染、图片模式（严格限制大小 $\le$ 512KB 与像素分辨率 $\le$ 512×512）与自动平滑降级。
  - **动态表单组件系统**：文件选择器（`file_picker`）、滑块（`slider`）、下拉单选（`select`）、数字框（`number`）、文本域（`text`）。
  - **动态联动条件 (`visibleIf`)**：实现复杂参数折叠与多模式切换。
- **3 个完整实战项目源码**：包含从零编写到上架全过程。
- **本地自动化校验与打包指引**。

---

## 📁 目录结构说明

```text
Toolbox-Community-Registry/
  ├── docs/
  │     └── PLUGIN_DEVELOPMENT_GUIDE.md   # 【核心】模块全栈开发与规范指南
  ├── plugins/                            # 社区模块源码与清单目录
  │     ├── gemini-banana-watermark/      # 各模块独立子目录
  │     │     └── manifest.json           # 模块配置清单
  │     ├── universal-wasm-runner/
  │     └── universal-data-codec/
  ├── packages/                           # 自动化构建输出的 .zip 模块包
  ├── registry/
  │     ├── index.json                    # 客户端在线拉取的多源聚合索引
  │     ├── app_version.json              # 客户端本体最新发版检测元数据
  │     └── ping.json                     # 节点连通性与测速探针
  ├── tools/
  │     └── build_registry.py             # 本地与 CI 自动化校验、打包与聚合脚本
  └── .github/workflows/
        └── build_and_sync.yml            # GitHub Actions 自动审查与同步流水线
```

---

## 🚀 如何为百宝箱贡献新功能？(快速上手)

贡献一个新工具非常简单，仅需 5 步：

```mermaid
flowchart LR
    A["1. Fork 派生本仓库"] --> B["2. plugins/ 新建模块目录"]
    B --> C["3. 编写 manifest.json 与脚本"]
    C --> D["4. 运行 python tools/build_registry.py"]
    D --> E["5. 提交 PR 发起合入申请"]
```

### 第一步：Fork 本仓库
点击右上角 `Fork`，将本仓库派生至您的个人空间并克隆到本地。

### 第二步：添加插件目录
在 `plugins/` 目录下新建以模块 ID 命名的英文小写文件夹，例如：
```bash
mkdir plugins/my-awesome-tool
```

### 第三步：编写 `manifest.json`
根据 [Manifest v2.0 规范](docs/PLUGIN_DEVELOPMENT_GUIDE.md) 编写配置文件，并可附带 SVG 矢量代码图标或脚本：
```json
{
  "id": "my-awesome-tool",
  "name": "我的炫酷工具",
  "version": "1.0.0",
  "minAppVersion": "1.0.0",
  "category": "text",
  "platforms": ["universal"],
  "description": "详细阐述本工具的核心功能、算法特点与适用场景，支持在客户端中被深度检索。",
  "author": "您的昵称",
  "executionType": "quickjs",
  "engineType": "quickjs",
  "icon": {
    "type": "code",
    "data": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\"><circle cx=\"12\" cy=\"12\" r=\"10\" fill=\"#3B82F6\"/></svg>"
  },
  "inputs": [
    {
      "id": "sourceText",
      "label": "输入需要处理的文本",
      "type": "text",
      "required": true
    }
  ],
  "action": {
    "handler": "quickjs_runner",
    "params": {
      "scriptFile": "index.js"
    }
  }
}
```

### 第四步：本地一键构建与规范审查
运行内置自动化工具，验证配置格式与图标合规性：
```bash
python tools/build_registry.py
```
> 若验证无误，脚本会自动打包生成 `packages/my-awesome-tool.zip` 并更新 `registry/index.json`。

### 第五步：提交 Pull Request (PR)
将修改提交并向 `main` 分支发起 Pull Request。
- GitHub Actions 将自动触发代码合规与安全扫描。
- 审核合入后，所有百宝箱用户在打开应用时即可在「模块市场」中即时发现并一键安装您的新工具！

---

## 🌐 多源镜像加速节点

客户端默认在后台自动并发测速并选择最佳节点，若某节点被墙或限流，将自动无缝切换：

| 节点类型 | 节点名称 | 镜像地址 |
| :--- | :--- | :--- |
| **国内极速源** | Gitee 官方镜像 | `https://gitee.com/sujiuovo/toolbox-community-registry/raw/main/registry/index.json` |
| **全球加速源** | jsDelivr CDN 免梯节点 | `https://cdn.jsdelivr.net/gh/SuJiuOvO/Toolbox-Community-Registry@main/registry/index.json` |
| **官方直连源** | GitHub Raw 节点 | `https://raw.githubusercontent.com/SuJiuOvO/Toolbox-Community-Registry/main/registry/index.json` |

---

## 🔒 社区安全与合规准则

为了保护所有百宝箱用户的设备安全与个人隐私，所有提交至本仓库的模块均须遵守以下安全红线：
1. **纯本地离线执行原则**：严禁在模块内植入任何未经声明的云端数据回传、用户隐私窃取或网络嗅探行为。
2. **源码清晰无混淆**：QuickJS 脚本与自动化脚本请保持代码可读性，不得恶意混淆或加壳。
3. **大文件外链化**：单个模块源码包建议小于 10MB。若需使用体积巨大的第三方 CLI 预编译程序（如 FFmpeg），请配置 `nativeRunner.downloadUrls` 结合 SHA256 校验远程按需静默下载，切勿直接向 Git 提交数十兆的二进制。

---

## 📄 开源许可证

本项目基于 [MIT 许可证](LICENSE) 开源发布。欢迎广大开发者共同建设更好用的百宝箱生态！
