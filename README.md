# Multi-Toolbox 社区功能模块仓库 (Toolbox-Community-Registry)

> 🚀 跨平台动态可扩展百宝箱（Multi-Toolbox）官方社区功能仓库。  
> 支持 **Gitee (国内高速镜像)** 与 **GitHub (国际节点 / jsDelivr CDN)** 实时双向同步。

---

## 目录结构说明

- `plugins/`: 社区功能模块源文件及清单（各模块独立目录）
- `packages/`: 自动化打包生成的 `.zip` 插件包
- `registry/index.json`: 供百宝箱客户端拉取的聚合清单（包含版本、多节点下载地址、哈希校验码）
- `registry/app_version.json`: 百宝箱客户端本体在线检测升级清单
- `tools/build_registry.py`: 本地与 CI 自动化校验、打包与索引聚合脚本

---

## 如何为百宝箱贡献新功能模块？

欢迎广大开发者为 Multi-Toolbox 提交实用、有趣或专业的新工具！

### 第一步：Fork 本仓库
在 GitHub 上点击 `Fork` 派生本仓库到您的个人空间。

### 第二步：添加插件目录
在 `plugins/` 目录下新建一个以您模块 ID 命名的英文小写文件夹，例如 `plugins/my_awesome_tool/`。

### 第三步：编写 `manifest.json`
在您的文件夹下新建 `manifest.json`，并遵循以下规范：

```json
{
  "id": "my_awesome_tool",
  "name": "我的酷炫工具",
  "version": "1.0.0",
  "minAppVersion": "1.0.0",
  "category": "image",
  "description": "详细介绍该模块的核心能力、处理算法和使用场景，支持在客户端中被深度检索。",
  "icon": "transform",
  "author": "您的昵称或 GitHub 用户名",
  "engineType": "native_image",
  "platforms": ["universal"],
  "inputs": [
    {
      "id": "param1",
      "label": "参数设置",
      "type": "text"
    }
  ],
  "action": {
    "handler": "image_custom",
    "params": {}
  }
}
```

### 第四步：本地测试与验证
运行脚本验证配置格式：
```bash
python tools/build_registry.py
```
若格式无误，将自动打包生成 `packages/my_awesome_tool.zip` 并更新 `registry/index.json`。

### 第五步：提交 Pull Request (PR)
将修改提交并向 `main` 分支发起 PR。GitHub Actions 将自动执行安全与格式审查，管理员审核合入后，所有百宝箱用户即可在客户端「模块市场」中即时发现并一键安装您的新工具！

---

## 多源镜像节点地址

- **国内 Gitee 极速源**: `https://gitee.com/sujiuovo/toolbox-community-registry/raw/main/registry/index.json`
- **全球加速 CDN (jsDelivr)**: `https://cdn.jsdelivr.net/gh/SuJiuOvO/Toolbox-Community-Registry@main/registry/index.json`
- **GitHub 官方源**: `https://raw.githubusercontent.com/SuJiuOvO/Toolbox-Community-Registry/main/registry/index.json`
