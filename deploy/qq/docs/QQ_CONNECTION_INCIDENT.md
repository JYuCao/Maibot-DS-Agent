# QQ 掉线排查记录

2026-10-24，用户报告频繁掉线并提供 [NapCat issue #2085](https://github.com/NapNeko/NapCatQQ/issues/2085)。经用户明确同意，已执行 `deploy/qq/compose.sh stop napcat`，停止 QQ 客户端及其登录重试。没有删除登录态，没有切换或重登账号。

## 本机证据

- NapCat 4.18.41；Linux QQ `3.2.34-53644`；旧 MaiBot NapCat 适配器 1.4.1。
- 检查时 core、Qwen、CPU Embedding 均运行；NapCat/core 的 Docker RestartCount 都为 0。因此不能把此次 QQ 下线归因为容器反复崩溃重启。
- 北京时间 18:38 出现 `KickedOffLine`：“账号已在另一台终端登录”。这提示需要检查同账号的其他电脑客户端，但不能单凭它判断是否有人盗号。
- 20:32 再次出现 `KickedOffLine`：“当前登录已失效”。随后多次 `Login Error, ErrType: 1, ErrCode: 3`；最近一段约每 2 分钟一次。当前尚无权威材料将此错误码直接解释为封号。
- core 每 5 秒的适配器重连是本机 OneBot WebSocket 连接尝试，与 QQ 客户端约 2 分钟一次的登录失败应分开判断。
- 日志里包含群友讨论“风控”的普通消息，不能将关键词命中数当成平台风控次数。本记录只采用系统事件，不收录群聊原文、登录凭据或令牌。
- 新社交生活插件未挂载、未加载、enabled=false，新增主动发言和日记投递均未授权，不是本次掉线的触发来源。

## 上游现状及迁移判断

issue #2085 当前正文链接指向 [SnowLuma](https://github.com/SnowLuma/SnowLuma)，不是一个可直接照抄的 NapCat 调参修复。旧适配器本机 Manifest 已标注停止更新，并建议使用 SnowLuma 适配器。

MaiBot 的 [统一 SnowLuma 适配器](https://github.com/Mai-with-u/MaiBot-SnowLuma-Adapter) 当前 Manifest 1.1.8 声明支持 Host 1.2.0–1.3.99 / SDK 2.5.0–2.99.99，版本范围涵盖本机。声明依赖 silk-python>=0.2.8，需在实施前核实容器依赖和网关冲突；版本范围相符不等于已完成集成验收。

该插件既可连接 NapCat，也可连接 SnowLuma。仅更换适配器并不会更换 QQ 客户端登录机制，不能承诺解决掉线。真正切换客户端需要独立 SnowLuma 运行环境、重新核对协议、账号、白名单、令牌和登录流程。

[SnowLuma 官方部署文档](https://snowluma.github.io/zh/docs/guide/deploy/docker) 支持当前 WSL2 + Docker 路线。实施建议为：新目录单独持久化数据，仅绑定本机管理端口，QQ 禁用 GPU，不复用正在写入的 NapCat 登录目录，不让两个实例同时登录相同账号。其容器要求 SYS_PTRACE 和 seccomp=unconfined，属于新增权限，尚未应用。

SnowLuma 仍是未获 QQ 授权的第三方客户端互操作项目；更换它不构成免风控或不封号保证。其许可、EULA、隐私条款与旧部署不同，尚未代用户接受，也未安装、启动或登录。

## 当前操作边界

1. 保持 NapCat 停止，不循环扫码，不清缓存或删除设备信息来试错。
2. 用户随后明确确认未登录其他设备，且 QQ 官方客户端已经显示风控警告。因此不再将真实多端互踢作为主要解释；此前的下线文案不足以证明存在另一台设备。
3. 若手机 QQ 显示明确验证或账号限制，按官方客户端提示由账号本人处理，不猜测解除时间。
4. 在确认方案、权限和新条款后，再准备迁移并逐项验收。先只读状态检查，不自动向真实群发测试消息。

查看状态：

```bash
deploy/qq/compose.sh ps -a
```

注意：普通 `compose.sh up -d` 会重新启动 NapCat。账号问题处理完毕前，不执行全栈启动或 NapCat 重启。需要单独维护本地模型时指定 `qwen`，不要带上 `napcat`。

保留目录：`data/qq/`、`docker-config/napcat/`、`data/MaiMBot/`、`data/MaiMBot-plugin-data/`。这些目录包含敏感登录态或聊天数据，不上传公开仓库。

## 相关 issue 检索补充

检索日期：2026-10-24。检索 MaiBot、NapCat、旧 NapCat Adapter、统一 SnowLuma Adapter 与 SnowLuma 的公开 issues；搜索结果、用户猜测、维护者判断与已验证修复分开看，不以 closed 状态代表风控已经解决。

| 来源 | 已核对的内容 | 对本机的意义 |
| --- | --- | --- |
| [MaiBot #1036](https://github.com/Mai-with-u/MaiBot/issues/1036) | 2025-06 用户因 NapCat 风控提出更换 Lagrange 接入，后来 not_planned；评论主要讨论当时的适配方式 | MaiBot 社区确有此类反馈，但旧架构的适配建议不能直接套到 1.3.15，也不是可量化的风控率证据 |
| [MaiBot #1858](https://github.com/Mai-with-u/MaiBot/issues/1858) | 2026-06、MaiBot 1.0.8、Docker SnowLuma；作者报告自我回复循环后被风控，并明确不确定是频繁更新还是循环导致；因自认重复而关闭 | SnowLuma 并非免风控方案；需要保留自身消息过滤，也不能断言本机存在同一旧 bug |
| [NapCat #2079](https://github.com/NapNeko/NapCatQQ/issues/2079) | 2026-09 报告无异地登录也反复登录态失效，ErrType 1 / ErrCode 3 约每两分钟一次；重新扫码、重启后仍会重现；10-05 项目 Member 回复归为风控 | 与本机表现最接近，支持按 QQ 会话/风控问题处理；没有给出固定参数或已验证根治补丁 |
| [NapCat #2085](https://github.com/NapNeko/NapCatQQ/issues/2085) | 2026-10-05 置顶、锁定，正文指向 SnowLuma | 可作为评估新客户端路线的线索，不是解除 QQ 账号限制的说明 |
| [MaiBot #1896](https://github.com/Mai-with-u/MaiBot/issues/1896)、[#1702](https://github.com/Mai-with-u/MaiBot/issues/1702) | 分别报告 Host 阻塞误杀插件 Runner、WebSocket 断开时回复重试 | 属于消息通道故障线索，不能据此解释 QQ 官方风控警告；更新心跳或模型不会解除账号限制 |

本机补查：适配器 `filters.ignore_self_message=true`；小号 OneBot 配置 `network.websocketServers[0].reportSelfMessage=false`，两处均保持原值。最近日志未检出 `Runner 健康检查失败` 或 Runner 强杀重启标记，但存在事件循环卡顿标记；后者是独立性能线索，不把它误判成官方风控的已知原因。此次没有为验证发送任何消息。

### 建议顺序

1. 保持自动化 QQ 客户端停止，账号本人按官方客户端具体警告完成验证或查看限制期限。没有证据支持统一的 24/48/72 小时解除承诺。
2. 在账号允许登录后，由用户选择仅用未加载机器人组件的官方 QQ 客户端作一次正常使用观察；若仍受限，优先通过官方账号安全/申诉入口处理，不靠更换 AI 模型、适配器或反复扫码试错。
3. 官方客户端恢复后，如果仍希望继续此实验，再评估独立 SnowLuma 客户端 + MaiBot 统一适配器；先停用自动发言，只核对登录/只读状态，保留回滚及数据。仅换适配器并继续连 NapCat 不改变底层登录机制。
4. 恢复机器人初期可先只允许管理员私聊和群内明确提及触发，保留单条发送、自身消息过滤；稳定后再逐项恢复自发参与和 @。这属于减少发送量与排查变量的建议，不保证避免平台限制，当前未修改这些设置。

未采用没有对照验证的“养号固定天数”、换 MAC、频繁换 IP、删除登录数据、盲目降 QQ 版本或换大号试错等做法。

## 已确认警告类型：登录设备的软件环境风险

用户提供原文：“设备存在外挂或其他软件影响QQ正常使用”。这是 QQ 对登录设备/软件环境的风险提示；不能仅据此证明 Windows 已感染恶意软件，也没有证据说明设备或账号被永久封禁。结合本机 NapCat 非官方接入，客户端接入方式是首要排查方向，具体检测对象和机制仍无法从提示中确定。

[NapCat #1057](https://github.com/NapNeko/NapCatQQ/issues/1057) 报告仅接收、不发送消息或调用其他 API 时，仍出现外挂/第三方工具提示及反复下线；更新 QQNT、NapCat 后未改善。该报告是社区个案，不是对本机因果关系的证明，但说明降低发言量不足以排除这类客户端风险。[2026-10-22 的 Discussion #2117](https://github.com/NapNeko/NapCatQQ/discussions/2117) 也报告外挂检测强制下线，检索时尚无回复或已验证修复。

因此暂缓客户端迁移试登：维持 NapCat 停止，按 QQ 官方提示处理验证/限制；需要恢复正常使用时，使用未加载机器人接入组件、来自官方渠道的 QQ。若干净官方客户端仍出现警告，由账号本人通过官方帮助入口处理。现有容器与数据保留，不自行删除 QQ 数据、扫描整台 Windows、卸载无关软件或修改机器标识。

SnowLuma 也是第三方互操作/Hook 路线，不能据“以官方 QQ 为底层”推断获得官方认可或免检测。迁移只作为用户充分知情后的可选实验，不能将解除当前设备软件环境风险作为预期保证。此次仅更新诊断记录，没有启动 QQ、迁移或发送测试消息。

后续开发状态：按用户“先补齐未完成功能”的指示，社交生活插件 0.2.0 已挂载并加载到 core，完成本地日记与管理接口验收；NapCat 仍停止，新的主动发送、私聊日记和空间操作保持关闭。首次排查时“插件未加载”的记录是当时状态，不代表当前状态。

恢复记录（2026-10-25）：用户明确表示已处理安全限制并授权接入。启动原 NapCat 容器后由用户完成扫码；00:48:20 OneBot 服务启动，00:48:24 MaiBot 适配器连接。只读 get_login_info 验证账号与配置机器人一致；没有发送测试消息或保存新 QQ 密码，没有启用新增 QQ 主动发送/日记投递。此恢复不代表已消除第三方接入风险，仍需观察长期稳定性。
