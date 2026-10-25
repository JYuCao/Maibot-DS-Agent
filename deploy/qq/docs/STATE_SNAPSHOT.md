# 部署源码快照（2026-10-26）

本次保存当前代码与部署说明，不改变运行服务，也不包含运行数据和凭据。

- 主程序：MaiBot 1.3.15；记忆归属与去重修复提交 `a336722cc`。
- 社交插件：0.8.0，独立仓库提交 `fa830634a867c410600845fb0491cdd6b9b49782`；完整历史已更新到下方 Git bundle。
- 新增四个交互插件的固定版本、构建依赖、配置模板与 Emoji 兼容补丁保存在 `deploy/qq/interaction/`。源码仓库与提交见 `plugins.lock.json`；依照锁定提交恢复独立仓库，Emoji 还需应用 `emoji-sdk-compat.patch`，不能仅拉取各仓库最新 main。
- 已保存冷场新话题提示、10–25 分钟空闲窗口、群聊 4 小时／私聊 1 小时冷却、21:00 日记及主人私聊优先取材。虚拟日程保留；日记成文仍使用本地 Qwen，人物归属和严格质量门槛的当前边界见 [私人日记机制](DIARY_MECHANISM.md)。
- 本地 Qwen 负责回复；其他模型任务仍按本机模型配置使用 DeepSeek，CPU Embedding 独立运行。
- QQ 登录状态不在 Git 中；恢复源码后仍需单独确认登录和适配器连接。快照不代表所有平台功能已通过在线验收。
- 部署模板使用保守初始值，不等同于本机当前实际配置。真实配置、密钥、空间凭据、数据库、日记、模型和 QQ 登录数据未提交。

## 恢复独立社交插件源码

为保持插件独立仓库结构，源码以完整 Git bundle 随主仓库保存。仅在目标目录不存在时，从主仓库根目录执行：

```bash
git clone deploy/qq/social/social-life-plugin.bundle plugins/social_life_plugin
```

不要对现有插件目录执行覆盖。后续插件变更需要先在其独立仓库提交，再重新生成 bundle 并在主仓库保存：

```bash
git -C plugins/social_life_plugin bundle create "$PWD/deploy/qq/social/social-life-plugin.bundle" --all
git bundle verify deploy/qq/social/social-life-plugin.bundle
```

仅恢复 Git 仓库不能恢复完整部署。私有配置和数据目录的备份范围、模型与镜像准备见 [部署与维护](DEPLOYMENT_NOTES.md)；这些内容需要单独安全备份，不应上传到公开 Git 仓库。
