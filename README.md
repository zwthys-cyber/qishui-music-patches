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

r1 构建和静态验证通过，但用户真机确认仍需完整播放广告，故未达到目标。r2 的修改依据和局限见 [分析记录](docs/ANALYSIS.md)。

r2 编译、八处补丁校验、签名和打包后对比均已通过：[Actions 39137795051](https://github.com/zwthys-cyber/qishui-music-patches/actions/runs/39137795051)。[下载 r2 实验版与验证报告](https://github.com/zwthys-cyber/qishui-music-patches/actions/runs/39137795051/artifacts/12140542384)。解压 Artifact 中的 `Qishui-21.2.0-TrollStore-experimental-r2.ipa` 并使用 TrollStore 覆盖安装，彻底退出 App 后重开。

r2 已收到真机失败反馈，视频仍需完整播放。现阶段没有已验证的完整去广告包；开屏路径与下一步运行时定位需求见分析记录。CI 成功不等于真机效果或服务端发奖成功。

## iPhone 15 Pro Max / iOS 17.0 的下一步定位

两版均未命中实际视频等待路径，现准备 [D1 设备观察构建](docs/PROBE.md)，确认实际安装版本、广告页类名及入口调用。D1 保留原广告行为，仅采集本机诊断日志；完整去广告目标尚未完成。
