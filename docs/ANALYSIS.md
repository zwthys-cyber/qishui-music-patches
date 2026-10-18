# 静态分析记录

输入：`com.soda.music_21.2.0_decrypted.ipa`；Bundle ID `com.soda.music`；版本 21.2.0；主程序 `SchubertAppStore`；ARM64；LC_ENCRYPTION_INFO_64 cryptid = 0。

精确 SHA256 和原始指令记录在 `patches.json`。目标文件的 __TEXT 映射基址为 0x100000000，所列目标在该 segment 内，虚拟地址减基址即文件偏移。

## 已定位的应用业务模块

- `STAd.IncentiveFlowService`
- `STAd.IncentiveServiceManager`
- `STAd.IncentiveOceanTask`
- `STAd.IncentiveFallbackPremiumTask`
- `STAd.IncentiveFallbackPremiumViewController`
- `STAd.IncentiveTimerService`
- `STPremium.RewardAdService`

注意：IncentiveTimerService 也包含听歌权益过期定时器，不能因名称含倒计时就直接停掉整个服务。本补丁没有修改该服务。

## 首版补丁依据

### 汽水兜底广告

`IncentiveFallbackPremiumViewController.fireWithTimer:` 位于 0x106fe1290，调用 0x106fe3670 跳板，再经 0x11593cee0 指向 0x106fe1114。

0x106fe1138 读取 double 倒计时；0x106fe1144 比较；0x106fe1148 的 `b.pl 0x106fe1218` 跳入递减和进度更新路径。落空路径调用现有计时清理、标记完成，并调用 countDownFinishHandler。首版仅将该分支替换为 NOP。没有直接改服务端成功响应。

### BDA 原生倒计时

`BDARewardedVideoAdController.continueCountDownText` 位于 0x100676f6c。0x100676fb0 的 `b.lt 0x100677048` 控制进入现有完成及清理路径。将它变成无条件跳转，不影响前面的暂停判断。新指令相对位移 0x98。

### BDA 视频模型

`BDARVADVideoInfo.effectivePlayTime`（0x1006a2d84）和 `effectiveInspireTime`（0x1006a2dcc）原本加载 ivar 后跳至共享 `ldr d0,[x0,x8]; ret`，因此返回类型为 double。只改这两个独立 12 字节入口，避免误改共享 getter、相邻 setter 或其他模型。

## 已找到的网络相关字符串

- `luna/advert/incentive/config`
- `luna/advert/incentive/done`
- `luna/advert/incentive/retrieve`
- `luna/ads/reward/settle`
- `luna/ads/reward/receive`
- `luna/commerce/validate_reward`
- `[incentive]` 的发奖校验参数失败提示

这些静态证据说明存在网络发奖/校验流程，但不能单凭字符串确定哪个入口的请求字段、服务端判定条件或最终权益状态。必须结合真机结果继续分析。首版是本地等待实验，不是已验证的免费听歌解锁。

## r1 真机反馈与 r2 假设

用户确认 r1 在“看视频全天免费听”入口中仍需完整播放，完整播放后才获得听歌权限。故 r1 **没有达到目标**。该反馈不能单独确定活动具体选择了哪个视频实现，也不能证明提前完成时服务端会接受发奖。

进一步静态分析发现：

- `BDARVLynxUIVideoNew.player:playbackTimeChanged:`（0x1006d4050）直接用回调参数生成 `progress` 毫秒值。它并不通过 r1 修改的有效时长 getter 计算该进度。
- `BDARVRefactorLynxUIVideoNew.videoPlayer:playbackTime:`（0x100723f84）存在相同的进度上报实现。
- 两个回调分别在 0x1006d40e0 / 0x100724030 用 `fmul d0,d8,d10` 生成 progress。此时 s9 已持有 ceil(duration * 1000)，下一步调用 numberWithFloat 构造字典中的 progress 值。对应 CFString 的内容已经静态解析为 `progress`，另一项为 `duration`。
- r2 将这两处指令替换为 `fcvt d0,s9`，使第一次正常进度事件达到全长。该改动是否覆盖用户路径仍需真机确认。
- 观看累计时间经广告播放器自己的 `durationWatched` 包装 getter 读取。r2 仅改 BDARVPlayer（0x100715a0c）与 BDASDKVideoPlayer（0x100758b78），返回 double 3600.0，尝试满足本地观看累计判断；没有修改通用 TTVideoEngine 或音乐播放器。

r2 保留 r1 四处补丁，总计八处修改。没有强制设置服务端成功响应，不能据此承诺发奖或完整音乐权限。CI 仍只负责指令、结构、签名和打包验证。用户看到的前置广告入口弹窗可能继续出现；本次实验针对进入视频后的等待。

## r2 真机失败后的范围修正

用户确认 r2 视频仍不能提前结束，并要求一并移除开屏广告。r2 没有达到目标，不能作为完整去广告版。

本轮静态分析新增证据：

- 主程序包含 `createRewardTabViewController()` 及默认 `hybrid://lynxview/` 地址，指向 bytegecko 的 `reward/reward/template.js`。已取得该公开模板进行静态阅读，模板内含背景 JavaScript、商业权益刷新和动态界面。该证据只说明存在额外页面路径，不能证明用户的广告视频具体经过哪个原生组件。
- `STAd.SplashServiceManager` 的布尔展示判断通过 0x1070e5854 跳板（指针 0x115942530）进入 0x1070e4428。其热启动调用点为 0x1070e40d4，返回 false 后进入原有不展示/收尾路径。尚未对冷启动和其他调用点做设备验证，不能声称完整移除开屏。
- 还存在 BDMannorSplashManager、BDASplashManager、STAd 内部广告源和缓存路径。直接在展示方法开头 RET 可能遗漏完成回调，导致启动或播控状态悬挂，不能作为通用修复。

下一步需要设备端的实际广告页类名、调用栈或入口/完成回调日志，确认当前安装包与被执行路径。现有环境无法连接用户的 iPhone；现有 UI 截图和两次失败反馈不能替代运行时证据。未将本轮静态定位包装成第三个“完整去广告”IPA。
