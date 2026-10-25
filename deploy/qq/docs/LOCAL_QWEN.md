# 本地 Qwen 回复模型

本次部署选择官方 `Qwen3-8B-Q4_K_M.gguf`，使用 llama.cpp 的独立 CUDA 推理容器。目标是先验证角色聊天体验，仅替换 Replyer；联网 Agent 的设计留待后续讨论。

## 组件分工

| 组件 | 模型 / 位置 |
| --- | --- |
| Replyer 角色回复 | 本地 Qwen3-8B Q4_K_M；别名 `qwen3-8b-local` |
| Planner 发言决策 | 原有 DeepSeek Flash |
| Memory / Utils | 原有 DeepSeek Flash |
| VLM 图片理解 | 原有 DeepSeek Flash 配置 |
| 文本 Embedding | 原有 CPU BGE 服务 |

这不是全离线部署。Planner、记忆摘要、图片等仍可能调用 DeepSeek，其他组件的 API 费用和数据发送边界不因 Replyer 本地化而消失。Qwen3-8B 是文本模型，不直接接收图片；当前人格文件、QQ 白名单和记忆隔离继续使用。

## 2026-10-24 实测结果

- 官方权重 SHA256 校验通过；容器内 CUDA 识别 RTX 4060 Laptop。
- 服务器在 8K 上下文、单并发配置下 healthy；整张显卡总占用约 6.1 GB，空闲约 1.8 GB，包含桌面等其他进程，不是 Qwen 独占用量。
- 两轮简单人设模拟分别约 1.28 秒、0.68 秒；短回复解码约 30–33 tokens/s。第二轮命中提示缓存，这些数字不是完整 QQ 回复延迟或长期吞吐承诺。
- 非思考输出、多轮请求和 MaiBot 原生 Replyer 调用通过，模型名确认 `qwen3-8b-local`；核心日志确认模型配置热重载完成。
- A-Memorix 仍为 `runtime_ready=true`、`retrieval_ready=true`、`degraded=false`；频率 0.20 和隐私隔离保持不变。
- 没有发送真实 QQ 测试消息；长期角色一致性、多人并发与长上下文质量仍待实际使用观察。模拟中仍可能出现重复白饭梗或括号动作，接入成功不等于已经消除这些表达问题。

## 固定来源与运行设置

- 模型、镜像和源码版本固定在 [`runtime.lock.json`](../qwen/runtime.lock.json)。
- 官方 GGUF 文件约 5.03 GB；下载器按官方 LFS SHA256 校验，权重保存在 `data/local-models/qwen3-8b/`。
- 推理容器：`maibot-qwen-server:b11854-cuda12`，来源为官方 llama.cpp CUDA 12.8 镜像。
- 上下文 8192 tokens、单请求并发、K/V 缓存 q8_0、Flash Attention、非思考模式。
- 模型文件大小不等于运行显存；显存还包含 KV 缓存、计算缓冲和其他应用占用。
- 当前固定版 llama.cpp 用服务器参数 `--reasoning off` 和 `--reasoning-budget 0` 关闭思考；不会沿用 DeepSeek 的 `thinking.type` 参数。旧的 `chat_template_kwargs.enable_thinking=false` 在此服务器版本已提示弃用，因此不再发送。
- 服务地址 `http://qwen:8080/v1`，没有宿主机端口映射或公网管理界面。

## WSL 与普通 Linux 的 GPU 接入

本机是 WSL2，已能通过 Windows 驱动访问 RTX 4060 Laptop。当前 Docker 没有 NVIDIA runtime；WSL 专用覆盖文件 [`qwen.wsl.yaml`](../qwen.wsl.yaml) 将 `/dev/dxg`、`/usr/lib/wsl/lib` 和 `/usr/lib/wsl/drivers` 显式映射给推理容器，驱动目录只读。WSL 的 libcuda 加载器依赖 drivers 目录，仅映射 lib 会导致 CUDA 初始化失败。此路径只适用于 WSL，已通过实际设备枚举验证，不要复制到普通 Linux。

普通 Linux 使用主编排的 `gpus: all`，需提前安装与驱动匹配的 NVIDIA Container Toolkit。统一入口 [`compose.sh`](../compose.sh) 根据是否存在 WSL GPU 设备选择覆盖文件，不会静默切换成 CPU 推理。

所有命令从 `~/MaiBot` 执行：

```bash
# 按固定版本下载并校验模型，支持继续未完成的下载
.venv/bin/python deploy/qq/qwen/download_model.py

# 启停与状态检查
./deploy/qq/compose.sh up -d --no-build --pull never
./deploy/qq/compose.sh ps
./deploy/qq/compose.sh logs --tail 80 qwen

# 不发 QQ 消息的离线人设、多轮及非思考检查
./deploy/qq/compose.sh exec -T core /MaiMBot/.venv/bin/python - < deploy/qq/qwen/check_qwen.py

# 先检查本地接口，再仅切换 Replyer
.venv/bin/python deploy/qq/configure.py --use-qwen

# 手动将 Replyer 切回已配置的 DeepSeek，不删除权重或记忆
.venv/bin/python deploy/qq/configure.py --use-deepseek
```

切换脚本保留其他模型组件与凭据，并首次保存 `docker-config/mmc/model_config.before-qwen.toml`。该备份包含原有 API Key，应与私密配置一样保管；文档不记录其内容。

本地服务失败时会正常暴露请求错误；没有添加自动转向 DeepSeek 的机制。切回 DeepSeek 后若不再需要占用显存，可单独执行 `./deploy/qq/compose.sh stop qwen`；下次切回本地前重新启动并检查该服务。

## 迁移与后续调节

备份范围增加 `data/local-models/`、`deploy/qq/qwen/` 和 WSL 覆盖文件。可以把 `maibot-qwen-server:b11854-cuda12` 一起加入原有 `docker save` 命令。换机器后需重新验证 GPU 驱动和显存余量。

先观察角色口吻、首句等待、多轮一致性和显存占用，再决定是否扩大上下文或替换更多组件。较长的搜索结果、记忆引用和聊天记录会共同占用 8K 上下文；本地接口接受的最大长度与 MaiBot 内部“上下文条数”是两种限制。

## 来源

- [Qwen 官方 GGUF](https://huggingface.co/Qwen/Qwen3-8B-GGUF)
- [llama.cpp Docker 说明](https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md)
- [llama.cpp Server 参数](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
