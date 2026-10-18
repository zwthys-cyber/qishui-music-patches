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
