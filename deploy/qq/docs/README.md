# QQ AI 角色文档

本目录集中维护这次 WSL2 + Docker Compose 部署的说明。适用版本为 MaiBot v1.3.15，部署基线提交 `062d45cf8`；配置数值以本机实际运行配置为准。

| 文档 | 用途 |
| --- | --- |
| [源码快照与恢复](STATE_SNAPSHOT.md) | 本次提交范围、独立插件 bundle 恢复方式和未包含的数据 |
| [交互插件](INTERACTION_PLUGINS.md) | 智能戳、表情选择、Steam、视频理解的配置、限制和维护 |
| [长期记忆与日记优化](MEMORY_DIARY_OPTIMIZATION.md) | 当前记忆分层审计、摘要窗口修正、两阶段日记、验证与回滚 |
| [私人日记机制](DIARY_MECHANISM.md) | 私聊优先取材、人物归属、选材与成文、独立预览和质量检查 |
| [部署与维护](DEPLOYMENT_NOTES.md) | 服务状态、配置路径、启停、日志、费用监测、备份迁移 |
| [AI 运行机制](AI_MECHANISM.md) | 如何收消息、决定发言、使用人格与上下文、形成和检索长期记忆 |
| [本地聊天](LOCAL_CHAT.md) | 无需 QQ 的聊天入口、人物关系、情绪、日记和身份隔离 |
| [本地 Qwen 回复模型](LOCAL_QWEN.md) | GPU 服务、模型来源、Replyer 切换、离线检查和迁移 |
| [人格与社交生活扩展](PERSONALITY_EXTENSION_NOTES.md) | 独立插件已加载、QQ 投递关闭、日记隔离、测试结果与待验收项 |
| [QQ 掉线排查](QQ_CONNECTION_INCIDENT.md) | 历史登录异常证据、恢复及迁移边界；本次状态另见源码快照 |
| [原始需求](REQUIREMENTS.md) | 保留最初的部署任务与 P0–P4 目标，不代表所有功能已经实现 |
| [记忆与日记需求](REQUIREMENTS-3.md) | 本次优化的目标与约束 |
| [扩展需求](REQUIREMENTS-2.md) | 人物关系、情绪、主动行为和独立日记需求 |

## 常用入口

- [独立 Compose 编排](../compose.yaml)
- [适配 WSL GPU 的统一启停入口](../compose.sh)
- [当前人格源文件](../personality.toml)
- [配置维护脚本](../configure.py)
- [不发送 QQ 消息的预检脚本](../check_api.py)
- [CPU Embedding 服务](../embedding/)

所有维护命令都从仓库根目录 `~/MaiBot` 执行。例如修改人格后：

```bash
cd ~/MaiBot
.venv/bin/python deploy/qq/configure.py --apply-personality
```

`personality.toml` 是可编辑的人格源文件；运行时读取 `docker-config/mmc/bot_config.toml`，需要通过上述命令同步。服务通常会热加载配置；必要时按维护文档重启 core。

模型 Key、WebUI 令牌和 QQ 登录状态保存在本地未跟踪的配置与数据目录中。文档只记录路径，不保存凭据。
