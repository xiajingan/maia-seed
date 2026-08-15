# Seed 架构

> Seed 是 Maia 的版本化 Python 技术共享包，也是其他 Python 工程启动迭代前的最小运行契约真源。

## 1. 定位与禁止项

Seed 提供无业务语义、可替换、可独立测试的横切能力。它不提供 Tenant、Account、Task 等领域模型，不访问业务服务/数据库，不管理 Helm release，也不封装 Kubernetes SDK。业务工程可依赖 Seed，Seed 不反向依赖业务工程。

## 2. 能力范围

| 包 | 能力 |
|---|---|
| `seed.config` | Pydantic Settings、文件/环境分层、Secret 引用、启动校验与配置摘要 |
| `seed.context` | 用户/服务/终端 principal，tenant/request/correlation 上下文传播 |
| `seed.errors` | 稳定错误码、retryable、用户提示、恢复动作及 HTTP/WS/消息映射 |
| `seed.events` | 版本化 envelope、事件 ID、Schema 注册接口和测试夹具 |
| `seed.state` | 通用状态机原语；具体业务状态由业务工程定义 |
| `seed.security` | principal 认证端口、脱敏、输入限制、重放/速率防护端口，以及无状态 `access-scope-kernel.v1` |
| `seed.crypto` | 加密/解密/轮换抽象；只接收由部署环境注入的 KeyProvider |
| `seed.secrets` | 解析数据库密码、第三方 token 等通用 Secret reference；SecretProvider 返回受生命周期约束、不可序列化/不可日志化的临时值 |
| `seed.audit` | AuditEvent 契约及风险分级的失败策略接口 |
| `seed.observability` | 结构化日志、OTel Trace、指标注册和关联 ID |
| `seed.runtime` | `/livez`/`readyz`、优雅停机、时钟/ID、有限重试、熔断状态机与 HTTP client 基线 |

依赖方向固定为：`config` 只解析 Secret reference；应用在调用点经 `secrets.SecretProvider` 取通用秘密；`security` 声明认证/脱敏策略并可依赖 `crypto` 接口；`crypto` 经专用 KeyProvider 取加密密钥。Provider 失败是 readiness/用例错误，秘密以短生命周期值出现且不可进入配置对象，配置摘要在取值前生成。

## 3. 云原生运行契约

应用只配置逻辑服务 URL，不感知 K3d/K3s/TKE。Seed 支持环境变量和挂载文件、Secret 文件引用、readiness/liveness、SIGTERM drain、连接超时/有限重试/熔断接口、资源与版本元数据。它不读取 Kubernetes API、不发现 Pod、不硬编码集群域名；服务发现由 Service/CoreDNS 完成。

### 3.1 内部模块分层

```text
kernel: ids/clock/result/state primitives
  ↓
contracts: context/error/event/audit
  ↓
ports: secret/crypto/auth/http/telemetry
  ↓
adapters(optional extras): fastapi/otel/httpx
```

Kernel 不依赖 Pydantic 以外框架；adapter 可依赖 contract，反向禁止。Context 使用不可变 request scope，异步任务显式序列化允许字段，避免 contextvar 泄漏到后台任务。

### 3.2 契约细则

- Error：`domain/code/retryable/user_message/recovery/correlation_id/details_ref`，details 默认不跨边界。
- Event：`eventId/eventType/schemaVersion/occurredAt/tenantId/actor/correlationId/payload`；未知字段策略和 upcaster 明确。
- Audit：actor/action/target/reason/before-after digest/result/risk；高风险审计失败默认阻止提交。
- Retry：仅对声明幂等的操作和白名单错误；full jitter、deadline budget、Retry-After；未知写结果转查询对账。
- State primitive：expected version CAS、允许迁移、终态；业务枚举只在所有者工程。
- Access scope：固定输入为 capability decision、direct/effective Own predicate、Creator/User membership 与版本，输出 allow/deny、scope 和来源；不包含 ManagerGroup 图、PermissionPolicy 或业务实体读取。Mud 负责 capability/effective Own，资源所有者负责本地 AccessMetadata 和最终调用。

### 3.3 版本和兼容

公开 surface 维护 API stability matrix。弃用先告警一个 minor，破坏变化升 major；事件 schema 与 wheel 解耦，消费者 migration manifest 记录最早/最晚版本。Seed 自身不提供旧业务 alias；兼容窗口结束删除 adapter。

## 4. 设计与发布

公开 API 经 `seed.*` 稳定入口暴露，Provider 使用 Protocol/ABC 注入；核心层只依赖标准库/Pydantic，FastAPI/OTel 等放可选 extra。包遵循语义化版本，锁定 Python 3.12+，产出 wheel、类型声明、SBOM 和签名。事件 `schemaVersion` 独立于 wheel 版本：生产者先发布可选字段或新版本，消费者验证并迁移，最后按登记版本停止旧事件；重放器在保留期内保留对应 decoder。破坏变更升主版本并附迁移和旧版本删除计划，不提供无限期 alias。

## 5. 质量门槛

pytest、mypy strict、Ruff 强制；Seed 仓库提供契约夹具和最小 FastAPI/消息样例，各真实消费者在自身 CI 运行兼容测试并回报版本矩阵，从而不产生 Seed 对业务工程的反向依赖。Test 样例运行在 K3d/K3s，覆盖配置挂载、Secret、探针、优雅停机和 Trace 传播。

每个 adapter 还需故障注入：Secret 不可用、OTel collector 不可用、SIGTERM 中途、HTTP timeout、重复事件、时钟偏差。日志/异常 snapshot 做 Secret canary 扫描。授权 kernel 由 Mud、Stem、Tea 及后续私有资源所有者在各自 CI 运行同一正反夹具；Seed 不连接这些服务，也不形成反向依赖。

产品路线：S0 kernel/contracts → S1 FastAPI/OTel adapters → S2 service client/retry/circuit → S3 consumer compatibility kit → S4 成熟 provider 扩展。Seed 版本按真实消费者需求演进，不建设“大而全基础平台”。
