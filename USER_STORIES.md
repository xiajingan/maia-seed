# Seed 用户故事

> 本文件是 Seed 独立迭代的需求真源；所有 P0 故事是其他 Python 服务业务开发的前置。

产品路线为 S0 kernel/contracts → S1 framework adapters → S2 reliable client → S3 compatibility kit。每个故事都必须有纯核心测试、adapter 测试、Secret canary 和至少一个真实消费者证据。

| ID | 用户故事 | 验收标准 | 来源 | 优先级 | 状态 |
|---|---|---|---|---|---|
| SEED-001 | 作为服务开发者，我希望有统一配置模型。 | 文件/环境/Secret 引用可组合；启动失败指出字段；输出摘要自动脱敏。 | FND-004/021 | P0 | `draft` |
| SEED-002 | 作为开发者，我希望传播身份与租户上下文。 | 用户/服务/终端 principal 分离；HTTP/消息上下文可验证；缺失租户默认拒绝。 | FND-001/003 | P0 | `draft` |
| SEED-003 | 作为消费者，我希望统一理解错误。 | code/retryable/userMessage/recovery 稳定；底层异常不外泄；各传输映射一致。 | FND-005 | P0 | `draft` |
| SEED-004 | 作为服务开发者，我希望发布和消费版本化事件。 | envelope 字段完整；Schema 正反例和幂等夹具可复用；破坏变更被 CI 拒绝。 | FND-005/020 | P0 | `draft` |
| SEED-005 | 作为安全负责人，我希望共享认证、加密、脱敏与重放防护端口。 | 三类 principal 认证隔离；Provider 可替换；轮换可审计；日志和异常不含秘密。 | FND-004/020 | P0 | `draft` |
| SEED-006 | 作为审计人员，我希望关键操作采用统一审计契约。 | 主体/动作/目标/理由/前后摘要/结果/关联 ID 完整；风险失败策略可配置。 | FND-003/005 | P0 | `draft` |
| SEED-007 | 作为运维人员，我希望统一日志、指标和 Trace。 | 关联 ID 自动注入；OTel 可跨 HTTP/消息传播；敏感字段过滤。 | FND-003/SOP-004 | P0 | `draft` |
| SEED-008 | 作为云原生服务，我希望提供健康探针和优雅停机。 | live/readiness 分离；SIGTERM 停止接流并 drain；测试验证无请求丢失。 | FND-021 | P0 | `draft` |
| SEED-009 | 作为服务开发者，我希望可靠调用其他服务。 | 强制连接/请求超时、有限重试、幂等判定、熔断/半开恢复及追踪；不提供固定 IP 发现。 | FND-020/021 | P0 | `draft` |
| SEED-010 | 作为发布负责人，我希望安全发布 Seed wheel。 | 语义版本、类型声明、SBOM/签名、兼容矩阵齐全；消费者契约通过。 | FND-020/022 | P0 | `draft` |
| SEED-011 | 作为架构负责人，我希望 Seed 保持无业务语义。 | 依赖检查阻止业务工程和领域模型反向进入；K8s 能力限于应用运行契约。 | ARCHITECTURE 3.2/6.1、FND-024 | P0 | `draft` |
| SEED-012 | 作为领域工程，我希望用通用原语定义自己的状态机。 | 合法/非法迁移、终态、并发版本和序列化可测；Seed 不包含 Task 等业务枚举。 | FND-006/020 | P0 | `draft` |
| SEED-013 | 作为服务开发者，我希望只在调用点解析通用 Secret。 | SecretProvider 支持文件/环境引用、失败可观测、值不可序列化或进入日志，生命周期结束可清理。 | FND-004/021 | P0 | `draft` |

## 产品化细化故事

| ID | 用户故事 | 验收标准 | 来源 | 优先级 | 状态 |
|---|---|---|---|---|---|
| SEED-014 | 作为开发者，我希望关联上下文不会泄漏到错误异步任务。 | background task 显式序列化允许字段；contextvar 生命周期清理；跨 tenant 并发测试无串扰。 | FND-003 | P0 | `draft` |
| SEED-015 | 作为调用方，我希望未知写结果进入对账而非盲重试。 | client 声明 idempotency/result query；deadline budget；超时 disposition 明确；测试只产生一次效果。 | FND-005/020 | P0 | `draft` |
| SEED-016 | 作为运维人员，我希望依赖故障反映到正确探针。 | live 不因依赖短断失败；ready 按关键依赖/排空状态；SIGTERM 先摘流后 drain。 | FND-021 | P0 | `draft` |
| SEED-017 | 作为维护者，我希望公开 API 变化可治理。 | stability matrix、deprecation warning、consumer range 和删除版本；无无限期 alias。 | FND-020/024 | P0 | `draft` |
| SEED-018 | 作为安全负责人，我希望自动发现日志中的秘密。 | fixture 注入 canary；日志/trace/error/audit snapshot 扫描；发现即 CI 失败。 | FND-004 | P0 | `draft` |
| SEED-019 | 作为资源服务开发者，我希望用唯一无状态算法合并权限事实。 | `access-scope-kernel.v1` 输入 capability/effective Own 与本地 Creator/Owner/User，输出 scope/来源；不持有策略或组图；Mud/Stem/Tea 运行相同正反夹具；破坏变化升 major 并有消费者迁移。 | FND-007～011/018/020 | P0 | `draft` |
