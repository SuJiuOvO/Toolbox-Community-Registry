# 富文本像素预览器 (`richtext-pixel-viewer`)

这是一个可独立安装和卸载的动态 WASI 插件。用户粘贴 Unity / TextMeshPro 风格的像素画富文本后，插件在本地解析颜色栈并导出真正的彩色 PNG，不需要修改 Multi-Toolbox 客户端。

## 支持的富文本

- `<color=#RGB>`、`<color=#RRGGBB>`、`<color=#RRGGBBAA>`，以及 `colour` / `textcolor` 别名。
- `</color>` 结束当前颜色并恢复上一层颜色。
- `<size=...>`、`</size>`、`<line-height=...>`、`</line-height>` 仅作为兼容标签忽略。
- `<br>`、`<br/>` 和换行符创建新像素行。
- `█` 或 `■` 表示一个有色像素；普通空格、全角空格和其他空白表示透明像素。

参考 `RichTextDisplay` 的颜色标签与方块格式保持兼容；插件不会执行任意 HTML 或脚本。

## 输出与限制

- 生成 `richtext_pixel_preview_<时间戳>.png`，透明像素可使用深色、浅色或真正的透明背景。
- 预览放大倍数可选 1–12；最终单边不超过 8,192 像素，总输出不超过 8,388,608 像素。
- 富文本最大 4 MB，源画布单边最大 4,096 像素，最大 1,048,576 个源像素。
- 无法识别的字符、未知标签、错误颜色值或多余的颜色结束标签会直接给出可读错误，不执行输入内容。

## 构建

```powershell
rustup target add wasm32-wasip1
.\build.ps1
```

Linux/macOS 可执行 `./build.sh`。构建脚本输出 `bin/richtext_pixel_viewer.wasm`；运行 `cargo test` 可执行解析、颜色栈和像素渲染单元测试。
