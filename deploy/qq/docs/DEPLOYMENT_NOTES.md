# QQ 角色部署记录

# 当前 QQ 已恢复接入（2026-10-25）

用户处理安全限制后明确授权恢复。已启动原 NapCat 容器，由用户扫码登录；00:48 左右只读检查确认登录身份为配置的机器人小号，认证 WebSocket、get_login_info 与 MaiBot 适配器连接通过。未发送 QQ 测试消息；本次未保存 QQ 密码，现有白名单和凭据配置未改。新日志暂未出现 KickedOffLine，长期稳定性仍待观察。

2026-10-25 经用户明确要求，已启用白名单群和管理员私聊的低频主动候选；日记投递仍关闭，普通白名单聊天继续可用。本地聊天不依赖 QQ，见 [本地聊天](LOCAL_CHAT.md)。历史排查与限制见 [掉线记录](QQ_CONNECTION_INCIDENT.md)。

更新时间：2026-10-25。实例目录：`~/MaiBot`。以下命令均在该目录执行。

文档入口：[QQ AI 角色文档](README.md)。原理说明见 [AI 运行机制](AI_MECHANISM.md)，最初的任务要求见[原始需求](REQUIREMENTS.md)。

## 版本与结构

- MaiBot：v1.3.15，提交 `062d45cf8`；以 `pyproject.toml` 为准，README 的版本标注已落后。
- 核心：官方 `sengokucola/maibot` 镜像，本地原始基底 `maibot-qq-core:1.3.15-062d45cf8`，当前实际运行的记忆修复镜像见文末记录。关键配置和记忆宿主源码哈希已与本仓库比对一致。
- NapCat：4.18.41，官方 Compose 所用的 `mlikiowa/napcat-docker`，本地固定别名 `maibot-qq-napcat:4.18.41`。
- 适配器：官方 `Mai-with-u/MaiBot-Napcat-Adapter` 插件 v1.4.1，提交 `d87203e2eff1835895ee34196b17a571dc6bbe24`。它兼容本版本，但上游已停止维护；没有部署旧式独立适配器进程。
- 编排：`deploy/qq/compose.yaml`。统一使用 `./deploy/qq/compose.sh`，脚本会为 WSL 添加 GPU 设备覆盖文件；根目录默认编排包含其他服务和不同的端口暴露方式。
- CPU 向量服务：FastEmbed + ONNX Runtime，`BAAI/bge-small-zh-v1.5`，512 维，2 CPU 线程；无 GPU 设备映射。
- 向量模型源：`Qdrant/bge-small-zh-v1.5`，固定修订 `46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59`，大文件按源站 LFS SHA256 校验。

## 当前状态与待办

- 已启动核心、NapCat、CPU 向量服务和 GPU Qwen 服务；核心 WebUI HTTP 200，向量和 Qwen 服务 healthy。
- Replyer 已切换到本地 Qwen3-8B Q4_K_M，非思考模式、8K 上下文、单请求并发；Planner、Memory、Utils 和 VLM 继续使用 DeepSeek。部署与切回说明见 [本地 Qwen](LOCAL_QWEN.md)。
- 已应用本人修改的“DeepSeek”鲸鱼娘人格；机器人账号、指定私聊账号和群号已写入本地配置。
- 已按本人明确确认记录当前 EULA / PRIVACY 的接受标识。
- 临时记忆写入、原会话召回与跨会话拒绝测试通过；正式记忆库未写入测试数据。
- 白名单离线检查通过；A-Memorix 自检显示 `runtime_ready=true`、`retrieval_ready=true`、`degraded=false`，向量维度 512。
- DeepSeek Key 已由本人填写，真实 API 极短请求通过（8 tokens）；自动摘要仍需积累实际聊天后验收。
- MaiBot 原生 replyer 调用链已使用本人新人格完成离线模拟回复验证；核心重启后日志确认“DeepSeek 已成功唤醒”，NapCat 自动重连成功。
- 首次账号注册出现过一次唯一键竞争，数据库已保存该账号；重启复查未再出现该错误，未为此修改主程序或删除数据。
- NapCat 已扫码登录；认证 WebSocket 与只读 get_login_info 检查通过，适配器已启用。真实 QQ 收发尚未发送测试消息验收。
- 白名单内正常入站消息可以触发真实回复。部署验证未向真实 QQ 群发送测试消息。

## 配置与后续调整（首次配置已完成）

1. 隐藏输入 DeepSeek Key（不要把 Key 发到聊天或写进命令行参数）：

   ```bash
   .venv/bin/python deploy/qq/configure.py --set-key
   ```

   Key 仅保存到忽略跟踪、权限受限的 `docker-config/mmc/model_config.toml`。当前版本未提供该字段的环境变量替换机制，因此没有使用无效的 `${DEEPSEEK_API_KEY}` 占位写法。

2. 在 Windows 浏览器打开 `http://localhost:6099/webui`，使用本机 `docker-config/napcat/webui.json` 中的 `token` 登录，然后扫码登录小号。
   已准备账号专属 `docker-config/napcat/onebot11_3353756021.json`：正向 WebSocket 监听容器内 `0.0.0.0:3001`，与插件令牌一致；3001 不映射到宿主机。若登录后未加载，重启 NapCat 或在管理页检查该正向 WebSocket 配置。

3. 验证并启用实际聊天：

   ```bash
   .venv/bin/python deploy/qq/configure.py --enable-qq
   ```

   此命令先验证向量服务、发起一次极短 DeepSeek 请求、只读查询 QQ 登录信息；全部通过才启用适配器。预检不发送 QQ 消息。启用后，白名单会话中的正常入站消息可能获得真实回复。若热加载未激活插件，重启 core。

4. 核心管理页：`http://localhost:18001`。登录凭据在本机 `data/MaiMBot/webui.json` 的 `access_token` 中；首次进入后按界面设置固定凭据。首次临时凭据会在核心重启后变化。

## 配置位置与调节

| 内容 | 路径 / 字段 |
| --- | --- |
| 人格源文件 | `deploy/qq/personality.toml` |
| 人格生效命令 | `.venv/bin/python deploy/qq/configure.py --apply-personality` |
| 主配置 | `docker-config/mmc/bot_config.toml` |
| 模型与私密 Key | `docker-config/mmc/model_config.toml` |
| 私聊与群白名单 | `plugins/MaiBot-Napcat-Adapter/config.toml` 的 `chat.private_list`、`chat.group_list` |
| 适配器开关 | 同文件的 `plugin.enabled` |
| 发言频率 | 主配置 `chat.reply_timing.talk_value=0.30`，低频参与普通群聊；这是原生频率参数，不是严格的每分钟限额 |
| @ 行为 | 允许回复时定向 @ 群成员：`enable_reply_at=true`；被提及/被 @ 的触发配置为 `mentioned_bot_reply=true`、`inevitable_at_reply=true` |
| 上下文 | 群规模参数 20、私聊 30；内部会话项不等同于固定数量的 QQ 原文；压缩摘要上限 2000 字符 |
| 回复与决策输出 | 模型配置：replyer 384、planner 1024、utils 1536、memory 2048 tokens |
| 连续发送 | 回复分割最多 2 条；自然合并连续入站消息；连续不发言后检查间隔逐步退避至 300 秒 |

同一个人格用于私聊与群聊；QQ 用户 ID、群号与群名/成员信息由原生适配器和聊天流管理器处理。没有自行生成资源归属 session hash。
图片理解分配给 DeepSeek Flash，尚待真实 API 验证；关闭了语音识别、图片长期记忆、表情包自动收集和额外 Agent/MCP 能力。本地 Qwen 使用独立 CUDA 推理容器，Embedding 仍使用 CPU；未额外安装 PyTorch 或下载浏览器。

群聊行为已补充为“合适话题偶尔接话，必要时才定向 @，避免连续提醒同一人”。群聊频率从 0.20 调到 0.30；私聊原生正常回复已启用，旧 private_talk_value 不生效。主动候选群聊每流至少间隔 240 分钟，私聊及本地私聊每流至少间隔 60 分钟；群、私聊及总每日配额均为 0（不限）；23:00–08:00 安静。只有近 6 小时内的真实话题、空闲 30–90 分钟后才有候选，同一最后入站消息最多一次，原生决策仍可不发言。配额是机会数，不是保证发送条数。@ 行为中的克制要求属于人格引导，不是新增的硬性次数限制。此次修改前的配置保存在本机 `data/deployment-config-backups/`。

## 长期记忆与隐私边界

2026-10-25 用户明确授权所有聊天记忆双向共享，包括已保存的 QQ 私聊和本地聊天内容；私人日记继续独立。当前 `a_memorix.global_memory_sharing_enabled=true`，普通聊天记忆、摘要、Episode 的跨流后置过滤均关闭。原有记录无需迁移或重新嵌入，写入仍保留来源，检索时开放全局范围。普通回复、白名单和各流短期上下文仍独立；不会把全部历史直接塞入 Prompt，也不会自动把 WebUI 身份绑定为某个 QQ 账号。

原生 `query_memory` 按需检索，默认返回 3 条。启发式自动召回、全局人物画像、人物事实写回、画像查询与注入已开启（每轮注入最多 1 人）。社交插件原始数据按会话保留，当前关系/情绪通过共享视图使用。表达、黑话共享组未改。尚未提炼成 A-Memorix 的原始聊天记录不会因开关自动补写。配置变更时，现存 2 条段落、3 条 Episode；实际群流与本地流均检索到 5 条命中，4 条记录共同可见，未输出正文或发送 QQ 测试消息。

纠错、合并、来源删除/恢复、遗忘和图谱维护使用 WebUI 的长期记忆管理功能。模糊修改不自动执行，聊天中一句“你记错了”不能保证旧记忆自动修正。记忆演化会影响强度、冻结和恢复，不等于完整原文按时物理删除。

私人日记仅在 `data/MaiMBot-plugin-data/jycao.social-life/diaries/`，不进入聊天记忆、Embedding、人物画像或 QQ 空间。日记投递授权关闭，空间已提供手动管理页；没有自动对外任务，写操作必须逐次确认。细节见 [AI 机制](AI_MECHANISM.md)。若以后恢复隐私隔离，必须同时关闭全局检索并恢复三类后置过滤；仅在人格中写“保密”不能实现权限隔离。A-Memorix 实现未改。

## 启停、日志与检查

```bash
# 启动（使用已经下载并固定的本地镜像）
./deploy/qq/compose.sh up -d --no-build --pull never
# 停止 / 重启 / 状态
./deploy/qq/compose.sh stop
./deploy/qq/compose.sh restart
./deploy/qq/compose.sh ps
# 日志：仅在本机查看；应用启动日志可能含管理凭据，不要原样对外分享
./deploy/qq/compose.sh logs --tail 100 -f core napcat embedding
# 离线服务检查 / 额外极短付费 API 检查 / QQ 只读检查
./deploy/qq/compose.sh exec -T core /MaiMBot/.venv/bin/python - < deploy/qq/check_api.py
./deploy/qq/compose.sh exec -T core /MaiMBot/.venv/bin/python - --deepseek < deploy/qq/check_api.py
./deploy/qq/compose.sh exec -T core /MaiMBot/.venv/bin/python - --qq < deploy/qq/check_api.py
```

容器设置 `unless-stopped` 自动重启；Docker 日志轮转为每服务 3 × 10 MB，应用日志保留 14 天/最多 10 个文件。WSL 已启用 systemd，Docker 服务已设置开机启动；自动恢复仍要求 Windows 已启动 WSL；本次没有配置 Windows 开机任务或禁止笔记本休眠。

本机管理端口仅 `127.0.0.1:18001`、`127.0.0.1:6099`。若 Windows localhost 转发不可用，先检查 WSL 配置和浏览器代理绕过 localhost，不要直接改成公网监听。独立 WebUI 开发服务才使用 7999；这里使用容器生产服务映射。

## API 消耗

角色回复已使用本地 Qwen，无该部分外部 API token 费用；决策、记忆处理等继续使用官方 `deepseek-flash`，显式关闭思考模式。DeepSeek 连接为 60 秒 API 超时、最多尝试 2 次（含首次）、失败等待 5 秒；本地 Qwen 为 90 秒连接请求超时、单次尝试，Replyer 总时限 120 秒。发言前的决策、图片识别和后台记忆也会消耗 tokens；当前没有硬性每日预算熔断。

用 WebUI 模型统计和 `data/MaiMBot/maibot_statistics.html` 查看调用/Token/估算费用，并以 DeepSeek 控制台账单为准。模型价格按 2026-10-24 官方人民币高峰价配置，空闲时间会高估。DeepSeek 官方 API 未提供 Embedding 模型；本地向量化无 API token 费用。

## 迁移与备份

先 `stop` 全部四个服务，再备份，避免 SQLite/WAL、向量和图谱快照不一致：

- `docker-config/`：机器人、模型、NapCat 配置及凭据；含本地配置备份 `mmc/old/`，也应保密。
- `data/MaiMBot/`：`MaiBot.db`、`a-memorix/`、媒体、管理凭据、日志和统计。
- `data/MaiMBot-plugin-data/`：插件持久数据。
- `data/qq/`：QQ 登录状态，视同敏感凭据。
- `data/embedding-models/`：CPU 模型，避免迁移后重新下载。
- `data/local-models/`：Qwen 官方 GGUF 权重与来源记录。
- `plugins/MaiBot-Napcat-Adapter/`：独立 Git 仓库、当前提交和私密 `config.toml`；主仓库忽略此目录，不会随主仓库提交。
- `deploy/qq/`（包含未跟踪的 `.env`）、本文件和主仓库提交号。

保留 UID/GID 1000 和目录权限，备份应加密存储。可用以下命令另存镜像，复制到 Linux 主机后 `docker load -i maibot-qq-images.tar`，避免依赖移动的 latest 标签：

```bash
docker save -o maibot-qq-images.tar maibot-qq-core:1.3.15-062d45cf8 maibot-qq-napcat:4.18.41 maibot-local-embedding:0.1.0 maibot-qwen-server:b11854-cuda12
```

源镜像配置 ID：core `9b075ae25b1fe1b292e69600dcb1adc4db18118410fd0b0f422d27ae8a0b8ea0`；NapCat `5548d626f39a470209fe55977ed14bc62cf026fb1143805d61a39060794a3832`。本地 Embedding 镜像由附带 Dockerfile、uv.lock 和同步导出的 requirements.txt 构建。

本机 Docker daemon 直连 Docker Hub 超时；本次通过终端现有代理下载并导入镜像，没有改动 Docker 全局设置。新机器首次构建向量服务前，可先运行 `.venv/bin/python deploy/qq/embedding/download_model.py` 下载校验模型。日常维护无需重建镜像或重新下载依赖。

## 事实来源

- [MaiBot 官方 Docker 部署](https://docs.mai-mai.org/manual/deployment/docker)
- [NapCat 适配器及维护状态](https://github.com/Mai-with-u/MaiBot-Napcat-Adapter)
- [DeepSeek 官方模型与价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)
- [DeepSeek 思考模式开关](https://api-docs.deepseek.com/guides/thinking_mode/)
- 本仓库 `src/config/`、`src/A_memorix/host_service.py`、`src/A_memorix/core/runtime/services/profile_admin_service.py` 及实际启动自检结果。

### 2026-10-25 人格与参与度调整

保留用户新改人格，补充“本鲸／鲸鲸”的自然自称偏好，不要求句句自称。群聊通常一两句，有内容可补充；私聊通常两到四句，按话题和对方节奏展开。社交扩展连续回复抑制从 90 秒 2 次、倍率 0.3 调为 75 秒 3 次、倍率 0.5；重复文本保护和拆分上限 2 保留。部署主模板版本 4，社交偏好模板版本 2（插件 Schema 仍为 0.3.0）。原配置备份在 `data/deployment-config-backups/whale-tuning-20261025-010626/`。

### 2026-10-25 主动间隔与全局记忆调整

本次覆盖前一节的日配额与冷却：群聊至少间隔 4 小时、私聊及本地私聊至少间隔 1 小时，无每日次数上限；保留 23:00–08:00 安静及无人回应不追问。社交插件 0.4.0、偏好模板版本 3、主部署模板版本 5。用户已明确允许私聊和群聊双向引用现存聊天记忆，私人日记独立。原配置及扩展源码备份：`data/deployment-config-backups/social-v04-20261025-011420/`。27 项离线测试、Ruff、插件受保护接口、记忆运行时与跨流检索通过。NapCat 未重启，未重新登录 QQ，未发送测试消息。

### 2026-10-25 共享社交状态与 QQ 空间（0.5.0）

- 主动聊天仍为群 4 小时/私聊 1 小时、无每日配额；夜间安静与不追问保留。
- `relationship.shared_across_sessions=true`、`emotion.shared_across_sessions=true`；同一 QQ 身份跨白名单 QQ 流共享，WebUI 不按昵称绑定 QQ。原始关系/事件未覆盖或迁移，按活跃日去重汇总。
- `cross_context.enabled=true`：私聊带入近 2 小时少量群聊背景；反向候选采样 0.10、每群 6 小时一次、至多一条 160 字符匿名背景。全局记忆仍允许查询私聊，风格引导不等于权限隔离。
- 人物画像、人物事实写回、查询和注入开启；每轮注入最多 1 人、证据 8 条、单轮刷新 5 人、队列批次 2 人。可能新增 DeepSeek 处理费用。
- 原生 WebUI“QQ 空间”：`/extensions/jycao.social-life/qzone`。默认目标白名单仅机器人和管理员；手动读取、发布文字、点赞/评论指定 ID。先本地预览，再弹窗逐次确认；没有自动任务。Cookie 仅在内存，禁止自动重新登录和请求重试。
- 已获准真实只读验收：自己空间返回 0 条动态。尚未真实发布/点赞/评论；需要管理员在页面逐次确认后验收。私人日记不参与空间内容和聊天检索。
- 配置模板版本：主 6、社交偏好 4、插件 Schema 0.5.0。源码和配置及一致性 SQLite 备份在 `data/deployment-config-backups/social-v05-20261025-012900/`。未修改主程序/A-Memorix 实现、模型任务或 GPU 配额，未重启 NapCat，未发送 QQ 群测试消息。

0.5.0 最终验收：33 项离线测试通过，Ruff 与原生 Manifest/WebUI Schema 校验通过；实际 core 共享状态和画像开关已确认，空间逐次确认拦截通过，真实只读返回 0 条动态；没有执行真实空间写入或 QQ 群测试消息。

### 2026-10-25 人物事实与画像修复

当前核心镜像：`maibot-qq-core:1.3.15-memory-fix-edbed3d2a9bd`；基底版本不变。`.env` 中 MAIBOT_IMAGE 已更新，日常启停命令不变。只有 core 因应用源码补丁被重建，NapCat、Qwen、Embedding 保持运行。

修复了分段回复重复提取、私聊“你”的受话者丢失、原文证据未校验，以及摘要人物归属未传入公共导入的问题。已为唯一可确认的旧管理员私聊摘要补齐归属并刷新画像；不恢复已删除事实、不改摘要正文。详见 [记忆排查与修复](MEMORY_DIAGNOSIS.md)。

新增持久化文件 `data/MaiMBot/a-memorix/person_fact_writeback.sqlite3` 记录证据处理状态，不保存原始聊天正文。备份时一并备份整个 a-memorix 目录；建议停止 core 后备份，包含必要的 SQLite WAL/SHM 或等待连接正常关闭。失败和中断的证据不会自动重新调用模型，排查时应检查 journal 状态与原始错误后再决定人工处理。

复验：`.venv/bin/python deploy/qq/memory/run_checks.py`。构建：`.venv/bin/python deploy/qq/memory/build_image.py` 仅传入源码和三语 Prompt；不会把本地密钥、配置或聊天送进镜像。改源码后须重新构建并更新 MAIBOT_IMAGE，单改宿主源码不会改变已经运行的镜像。迁移服务器时保留本地补丁源码、Prompt/元信息、构建脚本和 source.patch，单独检出上游同版本不包含此修复。

原始镜像和完整备份保留；退回旧镜像只用于定位问题，不会自动还原数据库，也会失去本次写回修复。不要自行删除软删除记录或覆盖数据库。

最终验证记录：40 项修复回归通过；新增三语 Prompt/元信息检查通过；附加检查 26 项通过。附加的全模板元数据检查有 1 项失败：已提交的英文 maisaka_replyer_document.prompt 在 HEAD 的 .meta.toml 中缺少说明条目，相关源文件本次未改。没有扩大修改无关模板。最终镜像为 maibot-qq-core:1.3.15-memory-fix-edbed3d2a9bd，运行容器全部补丁文件 SHA-256 已逐项确认。

### 2026-10-25 空间低频自动活动（0.6.0）

已按用户明确授权配置两组各 24–48 小时周期：发动态并回复下评、轮换浏览真实 QQ 好友并酌情点赞评论。自己每轮最多发 1 条、回复 2 条，好友每轮浏览至多 3 人并选择 1 条动态互动。周期错开至少 6 小时，写入间隔至少 30 秒；夜间安静、普通聊天优先，不补发、不自动重试或重新登录。日记投递仍关闭，私聊和日记不进入空间材料。

运行配置：`plugins/social_life_plugin/config.toml` 的 `qzone_auto`；安全模板版本 5 默认关闭自动授权。管理页 `/extensions/jycao.social-life/qzone` 显示排期、暂停状态、只读检查和公开内容预览。自动调度及去重保存在原有 `data/MaiMBot-plugin-data/jycao.social-life/social.sqlite3`，新增表不会重置旧状态。

当前 NapCat 空间票据接口返回空 Cookie，QQ 聊天登录正常，自动空间活动已暂停。本人已确认手机官方空间可正常进入。没有修改 NapCat、没有另行登录 QQ PC，也没有触发真实空间写入。

如选择独立官方网页授权：在浏览器打开 https://qzone.qq.com，用机器人小号扫码；从开发者工具 Network 中空间请求的 Request Headers 复制 Cookie 值。只在本机执行：

```bash
cd ~/MaiBot
.venv/bin/python deploy/qq/social/set_qzone_credentials.py
```

隐藏输入后仅保存四个必要 Cookie 字段，检查 uin/p_uin 都为机器人身份且有 p_skey；文件 `data/MaiMBot-plugin-data/jycao.social-life/qzone-credentials.json` 为 600。脚本明确将 credential_source 设为 local_file，但不解除暂停或发送消息。随后在空间管理页“只读检查连接”通过，再“核实后恢复排期”。不要把 Cookie 发给聊天或提交 Git；网页授权可能到期，到期需本人更新，程序不自动续登。napcat 与 local_file 不自动切换。

原插件源码/配置/一致性状态库备份：`data/deployment-config-backups/qzone-auto-20261025-024353/`。本轮仅修改独立社交插件及本地部署文档/模板，不改主程序或记忆修复镜像；未向 fork 自动推送独立插件。

#### 独立空间授权校验报错

隐藏输入脚本现区分：uin/p_uin 缺失、两者冲突、账号不匹配，以及 p_skey 缺失/为空；只显示字段状态，不显示字段值。可先用 `--check-only` 检查，不保存、不改配置、不连接空间。若冲突，请在无痕窗口仅登录小号后重新复制，不能手动把 Cookie 的账号数字改成小号。

复制位置为登录成功后 `user.qzone.qq.com` 请求的 Request Headers → Cookie；不要复制登录页、Response Headers → Set-Cookie、Application 表格或单个字段。浏览器操作后仍缺 p_skey 时，不应以 skey 或随意填写的值代替。原始 Cookie、p_skey 值都不能发到聊天。

### 独立网页授权已完成并恢复（2026-10-25）

本人在本机隐藏输入有效网页授权后，credential_source=local_file，凭据文件权限 600，只读空间请求通过。已解除空间自动暂停，首次 own 周期为北京时间 2026-10-26 09:56:58，friends 周期为 2026-10-26 19:33:58；后续分别随机 24–48 小时，安静/忙碌或休眠可能延后。没有立即补发，自动操作历史仍为空。

适配器和 NapCat 原始 get_friend_list(no_cache=true) 均返回成功且为空列表，不是适配器把已有列表解析丢失。当前好友互动无可用目标，每轮会重新读取真实好友列表；没有擅自添加好友。没有为了验收发布动态、点赞或评论。独立授权到期时会暂停并要求本人更新，不自动重新登录。
