# 汽水音乐 21.2.0 巨魔实验补丁

本项目针对指定解密 IPA 制作**实验版**。r1 真机反馈为仍需完整观看广告，未达到目标；r2 增加 Lynx 播放进度与广告播放器累计观看时长修改，但用户真机确认视频仍不能提前结束。两个版本均未达到目标。

编译、输入校验、补丁检查、签名检查和打包全部在 GitHub Actions 的 macOS runner 上运行。服务器仅准备源文件和进行静态分析，没有运行本项目的编译和验证流程。

## 修改范围

- 汽水 STAd 的兜底视频计时分支：首次计时回调进入现有完成逻辑。
- BDA 原生广告倒计时：首次未暂停计时进入现有完成逻辑。
- BDA 视频模型的有效播放和激励时长 getter：返回 1 秒。
- r2：两套 Lynx 广告视频回调在正常进度事件中报告全长。
- r2：两个广告专用播放器的累计观看时长 getter 返回完成值；没有修改通用音乐播放器。

不会直接伪造账号会员状态。正常发奖请求和服务端响应处理保留。是否真正获得听歌权益，需要真机确认；Lynx/动态下发广告流程也可能不受这些修改影响。

## 构建

输入 IPA 保存在本仓库的 `input-21.2.0` Release，未提交至 Git 历史。运行 Actions → Build Qishui 21.2.0 experimental TrollStore IPA，成功后从 Artifact 下载实验 IPA、SHA256 和 `verification.json`。

签名采用原有 entitlements 的 ad-hoc 签名，再交由 TrollStore 安装处理。参考 [TrollStore 官方说明](https://github.com/opa334/TrollStore)。安装使用原 Bundle ID，可能覆盖现有安装，请先保留原 IPA 和所需数据。

## 通过 CI 代表什么

CI 检查精确输入 SHA256、原始指令、指令位置、Apple 汇编输出、错误输入拒绝、修改范围、签名、ZIP、签名后各 section 字节及资源保持情况。它不代表真机启动、登录、音乐播放或服务端发奖通过。

真机需确认：启动和登录；触发“看视频免费听”；是否能提前结束；关闭页面后是否获得时长；完整播放原本需要广告权益的歌曲；重启后权益是否仍可用。若失败，需提供界面提示和具体触发入口，以区分本地广告路径未覆盖和服务端未发奖。

## 当前构建状态

**当前下载：[R3.1 IPA 直链](https://github.com/zwthys-cyber/qishui-music-patches/releases/download/r3.1/Qishui-21.2.0-TrollStore-R3.1.ipa)** / [发布说明与验证报告](https://github.com/zwthys-cyber/qishui-music-patches/releases/tag/r3.1)。

用户明确表示安装 R3 后仍导出 D1 格式日志，不能仅凭标签认定安装错误。R3.1 提升安装构建号至 100212041、隔离诊断类名和全局符号，并记录实际加载库；右上导出按钮为“日志 R3.1”。GitHub 编译和检查已通过，真实去广告与发奖仍待确认。详情见 [R3.1 排查记录](docs/R3.md)。

先从后台划掉汽水，再用 TrollStore 覆盖安装；打开后复现并从右上“日志 R3.1”导出 Qishui-Probe-R3.1.txt。无需先卸载应用。


r1/r2 均有真机失败反馈，不是完整去广告版。D1 日志已经确认实际页面为 STAd.SplashAdViewController 与 BDARVLynxViewController。

[R3 下载及验证报告](https://github.com/zwthys-cyber/qishui-music-patches/actions/runs/39141124019/artifacts/12141033639) / [修改依据](docs/R3.md)。R3 使用独立清单移除 r1/r2 八处等待改动，加入开屏展示资格修改，接入已确认控制器的真实首帧/SDK 完成/正常关闭链路。GitHub 编译、测试、签名和打包对比已通过，真机无开屏、视频提前结束及完整歌曲权限仍待验证。

用 TrollStore 覆盖安装 R3，彻底退出后重开，确认“日志 R3”。如失败，复现后导出 Qishui-Probe-R3.txt。前置广告权益入口弹窗可能继续出现；未宣称完整去广告目标已实现。

## iPhone 15 Pro Max / iOS 17.0 的下一步定位

两版失败后，已使用 [D1 设备观察构建](docs/PROBE.md)，确认实际安装版本和广告页类名；原始诊断说明保留供查阅。当前修改版使用上面的 R3。
