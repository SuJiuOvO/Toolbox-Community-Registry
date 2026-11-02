# 软件卸载

Windows 桌面端的交互式软件管理插件，需要 Multi-Toolbox 1.1.0。它提供软件登记信息、官方卸载器调用及卸载后的残留扫描与受控清理。

## 能力

- 通过 .NET RegistryKey 的 Registry32 / Registry64 视图读取 HKLM 与 HKCU 的 Uninstall 注册项。
- 按名称、发布者、登记体积、安装日期排序，按用户范围过滤；系统组件默认隐藏且禁止卸载。
- 点击软件后执行「卸载所选软件」，核对注册命令并确认；可选管理员权限，Windows 按需要请求 UAC 授权。
- 保留原 Windows 命令行参数；MSI 的 `/I` 维护操作改为 `/X` 卸载，保留其余参数。不会通过 cmd 或 Invoke-Expression 执行注册文本。
- 卸载程序退出后刷新列表，并自动扫描上次卸载软件的原安装目录、用户数据目录和卸载注册项。
- 残留项默认不勾选；用户核对路径并再次确认后才永久删除，失败项会单独报告。

## 边界

这是客户端内置交互视图的清单插件，功能代码在宿主的 `windows_uninstaller_service.dart` 和 `windows_uninstaller_page.dart`。不会执行 Win32_Product 查询，避免触发 MSI 修复。

残留扫描只覆盖与软件名称、发布者、安装目录和精确注册表路径相关的候选，不执行全盘模糊扫描。删除操作不进入回收站，安装目录可能包含共享文件，必须人工核对。受保护的系统目录、Windows 目录和危险注册表根会被拒绝。未知或含糊的卸载命令将拒绝启动，可使用 Windows 设置卸载。系统组件、NoRemove 条目没有卸载操作。

Microsoft Store / AppX 应用不在本版管理范围。体积来自 EstimatedSize 登记值，可能缺失或过时。部分卸载器会启动子进程后提前退出，因此退出码 0 只表示启动的程序结束，需结合刷新列表和卸载器界面确认结果。

## 验证

- `flutter test test/windows_uninstaller_test.dart`：注入假进程，覆盖参数解析、中文 JSON、权限失败、列表搜索及取消确认，不调用真实卸载器。
- `dart run tools/check_windows_inventory.dart`：Windows 只读枚举冒烟检查，不打印软件名称或执行卸载。

## 实现参考

- Microsoft Windows Installer: Uninstall Registry Key
- Microsoft .NET: RegistryKey.OpenBaseKey / RegistryView
- Microsoft .NET: ProcessStartInfo.Arguments / UseShellExecute / Verb
