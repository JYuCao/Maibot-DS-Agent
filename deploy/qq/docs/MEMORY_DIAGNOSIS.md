# 人物事实与画像排查

核查时间：2026-10-25 02:07 CST。仅只读检查运行配置、消息库、A-Memorix 元数据及源码；没有修改配置、源代码、现有记忆或画像，没有调用模型或发送 QQ 消息。

## 已确认结论

这是人物事实写回链路与画像证据接入的问题，不是容器掉线或数据库丢失。画像开关、查询和注入已经生效；开启后同时启用了 person_fact_writeback，暴露了原生写回的指代、幂等和证据归属问题。事实提取使用 Utils 的 deepseek-flash，不是本地 Qwen Replyer。

### 1. 私聊“你”没有绑定到明确的机器人身份

人物事实提取提示明确目标用户，却只将另一侧标成“机器人回复”，没有提供接收者的固定角色名、QQ 身份或“私聊直述中的你指机器人”的约束。只对“我/我的/自己”要求改写，对受话者没有同等实体规范化。

实际记录先后出现“用户曾为对方本地部署 maibot”和“用户给 DeepSeek 本地部署了 maibot”等近义表述。“对方”离开原会话后缺少明确身份；不能仅凭这两个字断言模型认为存在某个第三人，但它已经不是可靠的独立长期事实。

提示要求输出 evidence_message_id/evidence_quote，实际写回没有逐项核验这两个字段，而是将本次目标消息集合附给全部事实，并直接标为 direct_user/stable。仓库虽有 person_fact_verifier.py，运行写回链路没有调用它。“正在帮对方改记忆模块”这种当前活动也被标成稳定了解，显示稳定性准入不充分。

### 2. 同一回复分段导致重复提取，近义表述没有合并

2026-10-25 01:51:24 的一条私聊消息含第二人称“你”。01:51:28.951 和 01:51:29.200，机器人向同一证据消息发送两段回复。on_message_sent 对每个发送段分别 enqueue；事实服务不记录已处理的源消息集合。

01:51:30 写入三条使用“对方”的事实，01:51:31 又写入三条使用“DeepSeek”的近义事实；六条都绑定同一个真实用户消息 ID。没有证据表明是 QQ 重复投递或 Docker 重启造成。

外部写入 ID 根据 person_id + chat_id + 完整文本计算哈希；措辞不同会产生不同 ID。单次解析也仅按完全相同 fact 文本去重。因此分段重复提取与语义去重不足叠加。画像将稳定账本与分类证据合并时，去重仅限同一栏目内完全相同文字，还会让同一经历跨“关系设定／稳定了解／近期互动”重复展示。

### 3. 旧摘要可检索，但没有绑定人物，画像会排除

仍有效的两条旧聊天摘要中 person_ids 和 participants 均为空，其中一条包含用户部署、绘画等经历。摘要自动写回调用传入 participants=[]，没有补齐人物身份绑定。

画像的 _is_evidence_bound_to_person 明确要求 person_id/person_ids 或人物专属来源匹配。旧摘要即使正文包含昵称，也会在画像证据阶段被排除；这是防止同名串人的约束，不宜直接删除过滤。打开全局记忆共享只扩展检索范围，不会回填人物绑定。现有 historical_person_fact_reclassification 只处理已有特定人物 fact_claim 的分类，不扫描所有旧摘要做人物关联。

## 当前数据状态

- 9 条段落中：2 条旧摘要有效，7 条新增人物事实已软删除。
- 7 条事实的删除原因为 knowledge_base_record_delete，时间为 01:56:59–01:58:25；对应 7 个 claim 均 retracted。
- 7 个画像快照是同一人物的版本历史，不等于写入了 7 个不同人物。第 4/5 版确有重复表述；最新第 7 版在 02:00:37 更新，事实/证据列表为空。
- 刷新队列 done，原因 delete_admin_execute，没有重试错误。最新空画像符合“新事实已删除、旧摘要又未绑定”的状态，不能仅靠重新刷新解决。

## 建议修复顺序

1. 在私聊人物事实输入中显式标明用户、机器人及双方身份，处理直述/引用/转述的指代区别；不要全局替换所有“你”。逐条校验证据 ID、引用和目标人物，临时活动不要直接晋升稳定事实。
2. 基于真实用户证据消息做持久幂等，避免机器人回复拆分触发重复提取；使用明确的实体和事实键合并近义表述，新证据附加到同一事实。画像展示也需消除跨栏重复。
3. 基于旧摘要来源对应的真实聊天记录回填人物归属，先预览候选与证据；不按昵称字符串盲目认人。保留原摘要及审计记录，再刷新画像。
4. 对已软删除事实不擅自恢复或自动重建；先确认是否需要从原始证据重新提取，避免把用户的删除操作当作暂时缓存。

前三类修复需要主程序接入层和可能的 A-Memorix 上游改动；本次没有实施补丁，也没有清理或改写数据库。下一步应先以合成消息做定向回归，再准备可审阅的数据归属/合并预览。

## 源码定位

- src/services/memory_flow_service.py：_handle_message（每条发送触发、证据字段未逐条校验）、_extract_facts（提示缺少受话者绑定）、ChatSummaryWritebackService（participants 为空）、on_message_sent。
- src/person_info/person_info.py：store_person_memory_from_answer，以完整事实文本生成 external_id。
- src/A_memorix/core/utils/person_profile_service.py：_is_evidence_bound_to_person、_collect_vector_evidence、_merge_fact_claim_buckets、_append_profile_bucket。
- src/services/person_fact_reverification.py：历史处理范围仅限指定旧 fact_claim，非所有聊天摘要。

前三个关键运行源码已与实际 core 容器校验 SHA-256 一致；结论来自部署中的代码和记录。

## 已实施修复（2026-10-25）

已构建并部署独立本地修复镜像，Compose 的 MAIBOT_IMAGE 指向新镜像，原始官方基底保留。源码清单和哈希在 `deploy/qq/memory/patch_manifest.json`，可审阅补丁在 `deploy/qq/memory/source.patch`。

- 人物事实按真实会话/人物/用户证据消息做持久幂等；机器人分段、重启不重复提取，同源已删除的旧事实不会被自动重建。
- 模型仅选择有消息 ID 的原文直接自述；正文从经核对的原文构造。只对已经排除引述/转述的私聊直接自述绑定“你/您”为机器人实际昵称。含糊受话者、临时活动、假设、反问和同句限定被截断的内容不晋升稳定事实；不依赖模型把“对方”猜对。
- 每条事实只绑定实际支持它的消息 ID。非法输出和写入失败明确记录失败状态，不伪装成成功，也不自动再次收费重试。
- 新私聊摘要提供经过真实账号确认的人物归属，并在公共导入链路传递 person_ids/participants；群聊不按昵称或整个群的参与者猜测归属。
- 画像跨栏目去重保留稳定账本优先；仍不承诺任意近义改写都能被规则识别或每条聊天都形成记忆。
- 旧数据预览确认 1 条管理员私聊摘要可关联；仅补齐其 metadata 并排队刷新。另一条群聊摘要保持原样。摘要正文、原向量和 7 条删除标记均未改。

实际验收：最新第 8 版画像已引用这条旧摘要，未重新引用任何已删除段落或撤回 claim；没有“对方”表达，也无跨栏目完全重复条目。容器内持久去重初始化验证了旧证据被抑制。合成私聊通过现有 Utils API 验证“我给你部署了MaiBot”转换为“测试用户给DeepSeek部署了MaiBot”，没有写入测试事实或发送 QQ 消息。CPU Embedding、NapCat 认证 WebSocket 与只读登录检查通过。只重建 core，未重启 NapCat 或 Qwen。

验证脚本：`deploy/qq/memory/run_checks.py` 使用临时实例和离线测试配置；`check_extraction.py` 是可选的一次真实 Utils API 检查，会有 API 消耗；`repair_attribution.py` 默认预览，写入要求 core 停止并校验预览后数据未改变。

A-Memorix 的实现层仅保留两个局部兼容修复：summary_importer 传递已有身份字段、person_profile_service 跨栏目去重。其余修复在 MaiBot 接入层。依据 MODIFICATION_POLICY.md 的临时兼容补丁例外实施，后续应优先向上游 MaiBot_branch 同步；本次没有对外提交或运行格式化整理。

数据与原源码备份：`data/deployment-config-backups/memory-fix-20261025-021220/`。`a-memorix-before-apply/` 是核心停止后的完整元数据/向量/图谱备份；`attribution-preview.json` 和 `attribution-preview-applied.json` 保存修复前后元数据，均为本地私有文件。不能只恢复某一个数据库而忽略相配套的向量、图谱和删除状态。

最终验证记录：40 项修复回归通过；新增三语 Prompt/元信息检查通过；附加检查 26 项通过。附加的全模板元数据检查有 1 项失败：已提交的英文 maisaka_replyer_document.prompt 在 HEAD 的 .meta.toml 中缺少说明条目，相关源文件本次未改。没有扩大修改无关模板。最终镜像为 maibot-qq-core:1.3.15-memory-fix-edbed3d2a9bd，运行容器全部补丁文件 SHA-256 已逐项确认。
