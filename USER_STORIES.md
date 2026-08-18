# Seed 用户故事

> 本文件是 Seed 的公共能力输入真源，不是独立产品路线。外部工程通过统一 `dependency` Assignment 提出需求；Seed 自主接收、映射本地 Story、规划并执行 Sprint，再以 Delivery 更新交付状态。

能力成熟度为 S0 kernel/contracts → S1 framework/middleware adapters → S2 reliable client → S3 compatibility kit。Assignment 仅在 Seed 主动规划时进入本文件和 Sprint；`pending` 不等于已承诺，`planned` 必须关联本地 Story/Sprint，`delivered` 必须存在含精确 version + SHA-256 的 `dependency-package` Delivery。每个故事都必须有纯核心测试、适用的 adapter 测试、Secret canary 和消费者契约证据。

| ID | 用户故事 | 验收标准 | 来源 | 优先级 | 状态 |
|---|---|---|---|---|---|
| SEED-001 | 作为服务开发者，我希望有统一配置模型。 | 文件/环境/Secret 引用可组合；启动失败指出字段；输出摘要自动脱敏。 | FND-004/021 | 继承消费 Story | `draft` |
| SEED-002 | 作为开发者，我希望传播身份与租户上下文。 | 用户/服务/终端 principal 分离；HTTP/消息上下文可验证；缺失租户默认拒绝。 | FND-001/003 | 继承消费 Story | `draft` |
| SEED-003 | 作为消费者，我希望统一理解错误。 | code/retryable/userMessage/recovery 稳定；底层异常不外泄；各传输映射一致。 | FND-005 | 继承消费 Story | `draft` |
| SEED-004 | 作为服务开发者，我希望发布和消费版本化事件。 | envelope 字段完整；Schema 正反例和幂等夹具可复用；破坏变更被 CI 拒绝。 | FND-005/020 | 继承消费 Story | `draft` |
| SEED-005 | 作为安全负责人，我希望共享认证、加密、脱敏与重放防护端口。 | 三类 principal 认证隔离；Provider 可替换；轮换可审计；日志和异常不含秘密。 | FND-004/020 | 继承消费 Story | `draft` |
| SEED-006 | 作为审计人员，我希望关键操作采用统一审计契约。 | 主体/动作/目标/理由/前后摘要/结果/关联 ID 完整；风险失败策略可配置。 | FND-003/005 | 继承消费 Story | `draft` |
| SEED-007 | 作为运维人员，我希望统一日志、指标和 Trace。 | 关联 ID 自动注入；OTel 可跨 HTTP/消息传播；敏感字段过滤。 | FND-003/SOP-004 | 继承消费 Story | `draft` |
| SEED-008 | 作为云原生服务，我希望提供健康探针和优雅停机。 | live/readiness 分离；SIGTERM 停止接流并 drain；测试验证无请求丢失。 | FND-021 | 继承消费 Story | `draft` |
| SEED-009 | 作为服务开发者，我希望可靠调用其他服务。 | 强制连接/请求超时、有限重试、幂等判定、熔断/半开恢复及追踪；不提供固定 IP 发现。 | FND-020/021 | 继承消费 Story | `draft` |
| SEED-010 | 作为发布负责人，我希望安全发布 Seed wheel。 | 最终 version 的 wheel 只构建一次；签名/SBOM/provenance 与 SHA-256 固定；Test 验证的 digest 原样从 staged 提升 release；消费者锁定 version + hash。 | FND-020/022 | 继承消费 Story | `draft` |
| SEED-011 | 作为架构负责人，我希望 Seed 保持无业务语义。 | 依赖检查阻止业务工程和领域模型反向进入；K8s 能力限于应用运行契约。 | ARCHITECTURE 3.2/6.1、FND-024 | 继承消费 Story | `draft` |
| SEED-012 | 作为领域工程，我希望用通用原语定义自己的状态机。 | 合法/非法迁移、终态、并发版本和序列化可测；Seed 不包含 Task 等业务枚举。 | FND-006/020 | 继承消费 Story | `draft` |
| SEED-013 | 作为服务开发者，我希望只在调用点解析通用 Secret。 | SecretProvider 支持文件/环境引用、失败可观测、值不可序列化或进入日志，生命周期结束可清理。 | FND-004/021 | 继承消费 Story | `draft` |

## 产品化细化故事

| ID | 用户故事 | 验收标准 | 来源 | 优先级 | 状态 |
|---|---|---|---|---|---|
| SEED-014 | 作为开发者，我希望关联上下文不会泄漏到错误异步任务。 | background task 显式序列化允许字段；contextvar 生命周期清理；跨 tenant 并发测试无串扰。 | FND-003 | 继承消费 Story | `draft` |
| SEED-015 | 作为调用方，我希望未知写结果进入对账而非盲重试。 | client 声明 idempotency/result query；deadline budget；超时 disposition 明确；测试只产生一次效果。 | FND-005/020 | 继承消费 Story | `draft` |
| SEED-016 | 作为运维人员，我希望依赖故障反映到正确探针。 | live 不因依赖短断失败；ready 按关键依赖/排空状态；SIGTERM 先摘流后 drain。 | FND-021 | 继承消费 Story | `draft` |
| SEED-017 | 作为维护者，我希望公开 API 变化可治理。 | stability matrix、deprecation warning、consumer range 和删除版本；无无限期 alias。 | FND-020/024 | 继承消费 Story | `draft` |
| SEED-018 | 作为安全负责人，我希望自动发现日志中的秘密。 | fixture 注入 canary；日志/trace/error/audit snapshot 扫描；发现即 CI 失败。 | FND-004 | 继承消费 Story | `draft` |
| SEED-019 | 作为资源服务开发者，我希望用唯一无状态算法合并权限事实。 | `access-scope-kernel.v1` 输入 capability/effective Own 与本地 Creator/Owner/User，输出 scope/来源；不持有策略或组图；Mud/Stem/Tea 运行相同正反夹具；破坏变化升 major 并有消费者迁移。 | FND-007～011/018/020 | 继承消费 Story | `draft` |
| SEED-020 | 作为 Python 服务开发者，我希望复用可替换的 Redis 访问基础。 | 连接/关闭、健康检查、超时、序列化和观测可替换；业务工程自有 key/TTL/一致性语义；不形成全局 client 或业务缓存 API。 | 消费工程 Story/FND-021/022 | 继承消费 Story | `draft` |
| SEED-021 | 作为 Python 服务开发者，我希望复用 OceanBase 连接基础。 | Engine/Session 生命周期、连接池、健康检查和方言探测可独立测试；业务 Model/Repository/SQL/Alembic 留在所有者工程。 | 消费工程 Story/FND-021/022 | 继承消费 Story | `draft` |
| SEED-022 | 作为依赖需求提出者，我希望异步请求 Seed 公共能力。 | `dependency` Assignment 记录来源 Story/Task、目标行为、无业务语义边界和验收；不预填未知版本、不启动 Seed Sprint；Seed Response 必须自校验、绑定原 Assignment，接受时映射本地 Story。 | FND-020/022/024 | 继承 Assignment | `draft` |
| SEED-023 | 作为发布负责人，我希望跨仓库升级可迁移和回滚。 | 采用 add→migrate→remove；登记兼容矩阵、消费者、升级/回滚和旧入口删除版本；首次 Delivery 前配置组织真实信任根及签名/SBOM/provenance verifier，空配置必须 fail closed；Test/Production 不用 Git/path 依赖。 | FND-020/024 | 继承消费 Story | `draft` |

## Assignment 输入与迭代归属

- `docs/assignments/inbox/` 是 Seed 的统一外部输入池；Assignment 本体不可修改，Seed 独占响应和 Delivery 状态。
- `seed-dep-mud-p0-002-secrets` 是由 Mud Secret/APPManager Story `MUD-P0-002` 在迁移后补充的 `SEED-013` 真实输入，当前仅为 `pending`；现有源码不等于已纳入 Sprint 或可交付，必须由 Seed 后续主动接受并映射本地 Story/Sprint。
- Seed 只在用户主动规划时处理输入；接受后映射本地 Story/Sprint，不能由源工程远程启动。
- 通用维护或安全修复可由已知消费者 Assignment 或 Seed 本地 Maintenance Story 触发；必须登记影响面和迁移验证。
- Celt、Vine、Sage 不依赖 Seed；终端、Bridge、前端契约由各协议/服务所有者维护。
- 每个 `delivered` 结果必须先有有效 accepted Response，并绑定 Seed Sprint、源码提交、`dependency-package` Artifact、version + SHA-256、实际 extras、契约测试、升级与回滚结果；配置的 verifier 必须真实验证签名、SBOM 与 Build Once 并生成绑定 Delivery/Artifact 身份的受管 receipt。
