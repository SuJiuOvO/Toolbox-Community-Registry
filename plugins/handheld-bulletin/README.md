# 手持弹幕举牌

需要 Multi-Toolbox **1.1.0 及以上**，支持 Android 与 Windows。插件清单通过 `action.handler = handheld_bulletin` 打开客户端交互页面；它依赖新版客户端宿主能力，不能在旧版客户端独立热加载页面。

## 使用

打开插件后编辑文字，可换行；选择应援、接机、像素、告白预设，或调整字号、字重、字距、行高、文字及背景的六位 RGB 颜色。支持静止、左/右/上/下滚动，速度按逻辑像素每秒计算。静止时文字自动缩小以完整展示。可叠加霓虹光晕、空心描边、LED 点阵，开启水平镜像和 90° 倍数画面旋转。慢速闪烁默认关闭，周期 1–5 秒，对闪光敏感者请关闭。

点击“开始全屏举牌”进入展示。Android 可申请横屏并隐藏系统栏，Windows 切换系统全屏窗口。轻触画面显示或隐藏控制栏，可暂停、继续、返回编辑；键盘空格控制暂停，Esc 返回。展示期间申请屏幕常亮；退出后恢复先前常亮/Windows 全屏状态，Android 恢复系统方向和 edge-to-edge 模式。Android 大屏或系统策略可能忽略方向和隐藏系统栏请求，页面会保持可用。

设置经 SharedPreferences 存在本机，不上传数据。此功能不需要网络，也不会导出图像/视频。

## 开发

宿主实现：`lib/models/bulletin_settings.dart`、`lib/pages/handheld_bulletin_page.dart`。验证：`flutter test test/handheld_bulletin_test.dart`。
