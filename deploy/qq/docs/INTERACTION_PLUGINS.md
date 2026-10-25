# 交互插件（2026-10-25）

适用 MaiBot 1.3.15、SDK 2.16.0。四个插件为 `plugins/` 下独立 Git 仓库，通过 Compose 挂载；源码版本见 `deploy/qq/interaction/plugins.lock.json`。

| 插件 | 配置与实际策略 |
| --- | --- |
| Smart Poke 1.11.1 | `plugins/smart_poke_plugin/config.toml`。群聊和私聊响应被戳，概率 55%，同人同会话冷却 45 秒，每会话每分钟最多 2 次，回戳每次仅一下；LLM 使用本地 replyer，最多 96 tokens。 |
| 主动戳 | 仅允许群白名单；事件驱动概率 1%，同群冷却 4 小时、全局 30 分钟，08–23 时活跃，近 5 分钟至少 5 条消息，**每日次数不限**（`max_pokes_per_day=0`）。不主动戳私聊。 |
| 跟风戳 | 同一群白名单，概率 10%，冷却 10 分钟，随机戳发起者或被戳者。**不设每日上限**；成功触发时吞掉该通知，减少主链路重复回应。跟风和被戳响应不受主动戳的小时范围约束。 |
| Emoji Text Selector 2.1.0 | `plugins/emoji_text_selector/config.toml`。CPU Embedding 优先，512 维，30 分钟刷新；文本选择使用本地 replyer，上下文 12 条、候选标签上限 30，过滤内置 send_emoji。 |
| Steam 浏览 0.1.4 | `plugins/steam_browser_plugin/config.toml`。中国区、简体中文、请求超时 15 秒；按需查询，没有定时推送。商店、折扣与评价无需 Key；公开玩家资料、游戏库和最近游玩需要 Steam Web API Key。默认玩家留空，避免误把所有人当成同一玩家。 |
| 视频内容理解 2.1.1 | `plugins/content_understanding_plugin/config.toml`。群聊和私聊视频链接补充上下文，缓存 1 小时，B站和抖音解析开启。仅主人允许执行插件登录／登出命令；未配置任何站点账号凭据。 |

简单联网搜索已取消，没有安装到运行容器，也不需要 Tavily Key。此前下载的仓库随安装前备份移出 `plugins/`。Edge TTS 留待后续。

## 使用和后续凭据

- Steam：可以说“看看 Portal 2 现在多少钱”“最近有什么打折的合作游戏”。玩家查询需先在 [Steam 官方页面](https://steamcommunity.com/dev/apikey) 获取 Key，再执行 `.venv/bin/python deploy/qq/interaction/set_steam_key.py` 隐藏输入；不要将 Key 放进命令参数或聊天。
- 视频：发送 B站／抖音链接会补充上下文，不额外自动发解析卡片。不保证每个视频有摘要；B站官方 AI 总结需要账号登录态。需要时由主人使用插件 `/cu_login` 完成 B站扫码，或在本机 WebUI 的插件配置填写凭据；本次安装不执行登录，也不发送二维码。
- 表情：通过 MaiBot 原生注册接口启用了已有 30 张带描述、未禁用的表情；保留原文件和描述。原库注册前为 0 张；没有开启自动偷图或新增视觉模型。
- 智能戳：随现有 QQ 群／用户访问名单工作；它有独立限频，和社交生活插件的主动文字聊天冷却不共用。即兴回应不等同于完整长期记忆回复；实验性上下文回写保持关闭。

QQ 是否在线需单独检查。插件加载成功和只读测试通过，不等于已验证真实 QQ 发送。

本次验证：四个插件均为 `load_status=success`，WebUI 配置模型正常；Steam 上游自带 38 项测试、戳插件 3 项路由测试通过。表情文本路径已用真实本地 Qwen 验证，语义路径已用真实 CPU Embedding 和持久化缓存验证，发送端替换为内存 mock，没有向 QQ 发送测试消息。启动加载了 30 张表情，向量缓存初次产生 18 条去重描述（512 维）。原有社交与私人日记检查通过，NapCat 只读登录接口可达。

联网限制：B站公开视频基础信息查询通过，未登录因此没有验证官方 AI 摘要。Steam 的 DNS 正常，但容器请求遇到 `ConnectTimeout`；WSL 本机直连及已有 `127.0.0.1:7897` 代理测试也超时。Steam 插件保持已加载状态，配置没有猜填代理地址，没有开放额外端口；需要先确认本机 Steam 网络通路，才能验收实联网查询。

## 镜像、验证与维护

当前 core 镜像：`maibot-qq-core:1.3.15-interaction-v1`。基于原记忆修复镜像，只添加视频插件依赖；11 个新增传递依赖，没有升级原有包，也没有新增 GPU 服务。构建上下文不含运行配置或凭据。

```bash
cd ~/MaiBot
docker build --pull=false -t maibot-qq-core:1.3.15-interaction-v1 \
  -f deploy/qq/interaction/Dockerfile deploy/qq/interaction
.venv/bin/python deploy/qq/interaction/check_runtime.py
./deploy/qq/compose.sh ps
```

日常启停仍使用 `./deploy/qq/compose.sh stop` / `start`；查看核心日志使用 `./deploy/qq/compose.sh logs --tail 100 core`，不要公开粘贴未经脱敏的日志。

Emoji 插件只做两处兼容修改：`reply` 选项修正为 `replyer`，明确以 `task_name=` 调用模型。补丁保存为 `deploy/qq/interaction/emoji-sdk-compat.patch`。其他三个插件未修改上游源码。迁移时按 lock 文件恢复独立仓库并应用该补丁，另行安全复制实际配置和插件数据。

实际配置权限为 600，`config_back/` 已加入各独立仓库的忽略规则。Steam、视频、智能戳配置不进入 Git；Emoji 上游原本跟踪 `config.toml`，本机将其作为本地修改保留，不含外部凭据，更新前应备份并保留配置。不要把运行配置加入后续源码提交。插件数据持久化于 `data/MaiMBot-plugin-data/`；Emoji 向量缓存位于 `plugins/emoji_text_selector/.cache/`，可以重建。

安装前备份：`data/deployment-config-backups/interaction-plugins-20261025-141427/`，包括旧 Compose、私有环境和插件配置、注册表情前的一致性 SQLite 备份以及注册 ID 清单。该目录包含私有数据，不能提交 Git。回退时先按需恢复配置和旧镜像；不要直接用旧数据库覆盖已经产生的新聊天数据。
