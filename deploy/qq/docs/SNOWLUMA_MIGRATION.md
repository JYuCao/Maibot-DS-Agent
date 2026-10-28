# SnowLuma 替换 NapCat

工作分支：`feat/snowluma-migration`。2026-10-27 已完成本人首次设置与登录，SnowLuma、MaiBot适配器和现有核心服务已连通。没有向真实QQ发送测试消息。

## 当前组成与边界

- SnowLuma 官方发行版 **v2.2.1**，Linux/amd64，直接使用官方 Docker 镜像 `motricseven7/snowluma:v2.2.1`，未修改其程序或原生组件。实际镜像校验信息见 `../snowluma/image.lock.json`。
- 继续复用原生 `maibot-team.napcat-adapter`：它是正向 OneBot v11 客户端。API名称及日志中的 NapCat 字样保留，未另建适配器或改变 `platform=qq`、账号、scope、会话ID计算。
- 实际适配器配置 `plugins/MaiBot-Napcat-Adapter/config.toml` **只改 `napcat_server.host` 为 `snowluma`**。原令牌、白名单、通知和忽略自己消息设置均保留。
- Qwen、DeepSeek、Embedding、人格、A-Memorix、日记及空间授权配置没有变更。QQ空间仍使用已有独立本地票据，客户端更换不保证旧票据继续有效；不自动续登或重置。
- NapCat 服务保留在 `napcat` profile；SnowLuma 在 `snowluma` profile。统一入口按本机 `deploy/qq/gateway.local` 选择，未设置时本分支默认SnowLuma，`QQ_GATEWAY`环境变量可覆盖。不要手工同时启用两个QQ网关。

SnowLuma也通过原生QQ客户端的第三方桥接工作，更换软件不能保证消除账号风控。首次管理页需要本人确认发行包协议和隐私政策，之后修改初始密码；本次没有设置代为接受协议的环境变量，也没有修改主机ptrace系统设置。

## 端口与数据

| 用途 | 位置 |
|---|---|
| SnowLuma管理页 | `http://localhost:5099`，宿主仅127.0.0.1绑定 |
| QQ桌面／扫码 | `http://localhost:6081`，宿主仅127.0.0.1绑定 |
| 正向OneBot WebSocket | Docker网络内 `ws://snowluma:3001/`，Bearer令牌，不映射宿主端口 |
| OneBot HTTP | 配置中关闭；MaiBot动作通过同一Universal WebSocket调用 |
| 程序数据与配置 | `data/snowluma/app/` → `/app/data` |
| 新QQ客户端配置 | `data/snowluma/qq-config/` → `/app/.config` |
| 新QQ客户端数据 | `data/snowluma/qq-share/` → `/app/.local/share` |
| 本机迁移状态 | `data/snowluma/migration-state.json`，不含QQ密码 |

新QQ目录与旧 `data/qq/` 完全分离；未复制或覆盖NapCat登录数据，未把MaiBot数据库和私人日记挂给新网关。图片出站使用现有适配器的Base64编码，入站远程资源通过其原有下载链路读取。

SnowLuma禁用QQ GPU渲染，未分配GPU设备；2 CPU、2GiB内存上限、1GiB共享内存。仅按官方要求授予容器SYS_PTRACE及seccomp=unconfined，未使用privileged、host网络或挂载Docker socket。容器重启策略为unless-stopped，日志10MiB×3轮转。

## 首次人工操作

1. 在WSL本机终端查看初始凭据，**不要把密码或日志发到对话中**：

   ```bash
   docker logs maibot-qq-snowluma-1 2>&1 | sed -n '/初始登录凭据/,+8p'
   docker exec -u 0 maibot-qq-snowluma-1 cat /app/data/config/vnc-password
   ```

2. 在5099管理页以 `admin` 登录，阅读／确认该版本的 EULA 和隐私政策并按页面修改密码。协议与实际许可范围以官方文件为准；本次不代为勾选或更改授权／激活逻辑。
3. 在6081桌面进入官方QQ，手动扫码登录机器人小号。只登录该机器人，不要同时恢复NapCat；出现安全验证时按官方页面处理。
4. 登录完成后执行只读验证：

   ```bash
   .venv/bin/python deploy/qq/snowluma/probe.py --onebot
   ```

   该命令验证配置的小号身份、在线状态、版本、好友／群数量；不打印账号、联系人、Token或聊天内容，不调用发送／戳一戳／空间写接口。
5. 只读验证通过后恢复核心及已有模型：

   ```bash
   ./deploy/qq/compose.sh up -d --pull never core
   .venv/bin/python deploy/qq/social/check_runtime.py
   .venv/bin/python deploy/qq/interaction/check_runtime.py
   ```

   MaiBot运行后，原有已授权自动聊天、主动发言、戳和空间任务可能正常运行。没有用发送真实消息作为部署验收。

初始密码未修改就重启时，上游会生成新临时密码；不要使用旧日志中更早的值。不知道VNC密码时只在本机运行上述读取命令，不要公开5099、6081或凭据。

## 日常启停

从仓库根目录执行，首次创建使用up，日常保留容器使用start／stop：

```bash
./deploy/qq/compose.sh ps
./deploy/qq/compose.sh start
./deploy/qq/compose.sh stop
./deploy/qq/compose.sh restart core
./deploy/qq/compose.sh logs --tail 100 -f core
```

SnowLuma日志可能有初始密码及账号信息，需本机查看，不直接粘贴到公开报告。已有设备会话有效时不必为改人格、日记或模型而重启QQ网关。只需启动扫码界面时：

```bash
./deploy/qq/compose.sh up -d --no-deps --pull never snowluma
.venv/bin/python deploy/qq/snowluma/probe.py
```

## 回滚到原NapCat

先停核心与两个网关，再切换配置；切换脚本只改主机和本机profile选择，不覆盖其后更新的白名单或其他设置：

```bash
./deploy/qq/compose.sh stop core snowluma napcat
.venv/bin/python -m deploy.qq.snowluma.use_gateway napcat
./deploy/qq/compose.sh up -d --pull never napcat
# 本人确认旧QQ登录正常后再恢复核心
./deploy/qq/compose.sh up -d --pull never core
```

重新选择SnowLuma时同样先停两个网关，再执行 `use_gateway snowluma`，不要同时运行两个已登录的客户端。`QQ_GATEWAY=napcat ./deploy/qq/compose.sh ...` 仅临时选择profile，**不会同步改变适配器主机**，不能替代切换脚本。

分支切换只改变受Git管理的部署文件，不会恢复未跟踪的适配器真实配置或本地选择文件。回到main前应先完成网关回滚；不要认为 `git switch main` 会自动把QQ也切回去。

修改前备份：`data/deployment-config-backups/snowluma-20261027-202039/`，含原Compose、启动入口、适配器配置、私有env和会话身份元数据。原NapCat容器、配置、登录目录和镜像保留，未删除数据库或记忆。新主机迁移时，另行备份 `data/snowluma/`、实际适配器配置及本机gateway选择，权限保持私有。

## 镜像与下载

官方发布标签与amd64 manifest digest均已固定在image.lock.json。此次Docker守护进程直连Registry失败，改用宿主机已有代理和校验后的Google crane工具获取该digest对应镜像，再docker load导入；导入前检查原始config SHA-256，导入后逐项核对RootFS层、Entrypoint、Cmd、Env等与官方归档一致。

Docker29的containerd导入描述符digest与上游原始config digest用途不同，两个值均记录，未把两者不相同误判为镜像内容变化。导入镜像只赋予官方版本标签，没有构建自定义软件镜像。没有修改Docker daemon代理、DNS或重启Docker。crane仅存本地data/deployment-tools，不安装系统包。

`pull_policy: never` 防止未经校验漂移升级。新主机需先拉取／导入固定镜像；网络正常时从lock取完整digest：

```bash
docker pull motricseven7/snowluma@sha256:74d6874a4240636dca700734f31fbce7d0735cbce6bb43780dd8e3788eddccc9
docker tag motricseven7/snowluma@sha256:74d6874a4240636dca700734f31fbce7d0735cbce6bb43780dd8e3788eddccc9 motricseven7/snowluma:v2.2.1
```

## 验证记录与待验收

已通过：Compose两profile各自只选择对应网关；脚本静态检查；仅适配器主机改变的逐字段比对；容器健康；5099／6081 HTTP；本机端口绑定、无GPU、无privileged、独立数据卷检查。

离线协议验证通过：实际适配器的OneBot私聊／群聊文本入站、负数消息ID保持、QQ身份字段、出站文本／@／Base64图片编码、私聊／群聊白名单拒绝与放行。仅构造内存字典，网络调用0、真实发送0。v2.2.1源码存在当前所需friend_poke/group_poke/send_poke、poke通知及标准查询接口；这不等于已用真实账号验证了所有扩展接口。

已完成登录后只读验收：小号身份匹配、OneBot在线和查询成功；核心日志确认 `ws://snowluma:3001` 连接及QQ路由激活；原4个会话身份／scope保留；社交日记及4个交互插件加载检查通过；记忆runtime/retrieval ready且未降级。真实私聊／群聊收发、媒体下载、戳一戳和空间长时稳定性尚未主动发送测试验收。没有宣称替换能消除风控。

官方资料：[发行版](https://github.com/SnowLuma/SnowLuma/releases/tag/v2.2.1)、[Docker框架](https://github.com/SnowLuma/SnowLuma.Docker.Framework)、[OneBot接入](https://snowluma.github.io/en/docs/guide/connect-bot)、[配置](https://snowluma.github.io/en/docs/guide/configuration)、[EULA](https://github.com/SnowLuma/SnowLuma/blob/v2.2.1/EULA.md)、[隐私说明](https://github.com/SnowLuma/SnowLuma/blob/v2.2.1/PRIVACY.md)。


## 最终运行记录

SnowLuma `2.2.1-node`，容器Linux QQ软件包 `3.2.32-52194`，Node `v24.22.1`。好友／群只读查询计数7／3，仅1个既有允许群与1个既有允许私聊继续受原适配器白名单控制。核心、SnowLuma、Qwen、Embedding均运行；后3项Docker健康检查通过。原NapCat未删除、保持停止。匿名验证记录见 `../snowluma/verification.json`。部署源码保存在本迁移分支；私有配置与运行数据不进入Git。
