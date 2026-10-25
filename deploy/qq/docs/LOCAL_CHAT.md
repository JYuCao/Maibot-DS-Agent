# 不接入 QQ 的本地聊天

入口：[本地聊天室](http://localhost:18001/chat)。使用现有 WebUI 登录方式；不需要 QQ 扫码。选择默认本地聊天标签，直接与 DeepSeek 鲸鱼娘对话，无需开启虚拟 QQ 身份。

当前使用 MaiBot 原有本地聊天室，经过真实聊天核心、上下文、模型和记忆链路；不是单独绕过 MaiBot 的模型调试窗口。社交生活插件已更新为 0.5.0，支持原生 `webui` 默认私聊，未修改主程序或人格源。

## 能用的功能

| 功能 | 本地使用方式 |
| --- | --- |
| 人格、口吻、上下文 | 默认聊天室直接使用现有人设与本地 Qwen 回复模型 |
| 长期记忆 | 继续使用原生 A-Memorix，按真实本地聊天流隔离；长期摘要仍需达到原配置阈值，不是每句话都立即成为长期记忆 |
| 人物关系和短期情绪 | 同一份社交插件观察原生本地消息，不逐条增加 LLM 分析 |
| 虚拟生活 | 状态提示随时段变化；属于虚拟背景，不是现实线下经历 |
| 有限主动性 | 本地开关单独启用，仍遵守冷却、夜间安静、近期真实话题、每日上限和不追问；初期每个本地流最多 1 次/日，不会固定定时问候 |
| 日记 | WebUI 插件扩展“社交生活”页，或下方本地命令按日期查看/生成；不会通过聊天发送正文再回流到记忆 |

默认聊天室是私聊。群成员 @、多人群聊决策、QQ 图片投递、空间操作等，需要对应群/平台环境，不能将本地私聊结果当作 QQ 验收。

“本地交互”不等于全部模型离线：回复和日记使用现有本地 Qwen，Embedding 使用 CPU 服务；planner、记忆处理等仍沿用现有 DeepSeek API 配置，本次没有擅自切换模型任务。

## 身份与隐私

- 浏览器保存本地用户标识，后端使用 `webui_user_...` 和真实 `ChatSession.session_id`。更换浏览器、无痕模式或清除站点数据可能产生新身份，昵称本身不是持久身份。
- 本地身份与 QQ 小号/主人 QQ 不自动绑定；已按 2026-10-25 用户明确授权开启聊天长期记忆全局共享，含既有本地/QQ 私聊记忆；私人日记独立。身份本身仍不绑定。
- 仅支持经过 WebUI 鉴权的默认本地私聊。虚拟群和虚拟 QQ 身份不会自动获得本地身份权限。
- 本机已启用 `diary.include_local_private=true`，允许本地聊天经过敏感材料筛选后用于主人私有日记。日记只落在插件私有目录，不进入聊天检索、画像或 Embedding，不向 QQ 投递；不希望参与日记时可关闭此项。
- `proactive.local_sending_authorized=true` 仅授权本地机会；QQ 的 `proactive.real_sending_authorized=true` 已另获明确授权，`diary.private_delivery_authorized=false` 保持关闭。私聊及本地主动间隔至少 60 分钟，群聊至少 240 分钟，每日配额不限。

## 常用管理

在 `~/MaiBot` 执行：

```bash
.venv/bin/python deploy/qq/social/manage.py status
.venv/bin/python deploy/qq/social/manage.py generate
.venv/bin/python deploy/qq/social/manage.py diary --day 2026-10-25
.venv/bin/python deploy/qq/social/check_runtime.py
```

日记默认 23:10 起生成；当天已生成则不会覆盖或重复调用模型。文件位于 `data/MaiMBot-plugin-data/jycao.social-life/diaries/`。本地关系、情绪与生活配置位于 `plugins/social_life_plugin/config.toml`，也可在 WebUI 插件配置中调整；保持登录令牌私密。

core、Qwen、CPU Embedding 已运行。2026-10-25 用户另行授权后 QQ 已恢复接入；本地聊天仍不依赖 QQ。仅维护本地服务时明确指定服务：

```bash
deploy/qq/compose.sh up -d qwen embedding core
deploy/qq/compose.sh restart core
```

## 已做验证

- 25 项插件测试通过，包括本地真实流解析、与 QQ 的状态隔离、本地私有日记材料显式开关，以及本地主动授权不打开 QQ 授权。
- 通过原生已鉴权 WebSocket 建立独立本地验收会话，完成“我喜欢拼图”及下一轮回忆测试；收到两轮回复，插件记录到本地聊天流。
- 测试没有 QQ 登录或发送，测试内容保留在单独的“本地功能验收”身份下，不是浏览器里你自己的人物画像。
- 本地端到端验收脚本 `deploy/qq/social/check_local_chat.py` 会发起两轮本地模型对话并保留记录；日常仅检查服务和权限时使用无模型调用的 `check_runtime.py`。

0.5.0：本地私聊可读取少量近期群聊背景；总体情绪跨许可会话共享，但本地用户标识不会自动绑定 QQ。人物画像已启用，私人日记仍独立。QQ 空间仅在专属管理页手动使用，不会因为本地聊天自动发布动态。
