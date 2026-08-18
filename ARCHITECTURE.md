# Seed 架构

> Seed 是 Maia 的版本化 Python 后端公共基础库。它没有独立产品路线，但自主规划和执行由外部 Dependency Assignment 输入触发的 Maintenance Sprint。

## 1. 定位与禁止项

Seed 提供无业务语义、可替换、可独立测试的横切能力。它不是独立服务，不拥有产品需求、业务数据或独立部署拓扑。新增能力通常来源于后端消费工程写入本工程的 `dependency` Assignment；Seed 独立判断归属、映射本地 Story、规划 Sprint、实现测试并发布 Artifact，消费工程不直接修改 Seed Sprint。

Seed 不提供 Tenant、Account、Task 等领域模型或业务状态，不访问业务服务，不拥有业务 Schema/Repository/Alembic migration，不管理 Helm release，也不封装 Kubernetes SDK。业务工程可依赖 Seed，Seed 不反向依赖业务工程；禁止为“未来可能复用”提前抽象。

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
| `seed.redis` | 可选 Redis 连接、生命周期、健康检查、序列化与技术性锁/缓存端口；不定义业务 key、TTL 或一致性策略 |
| `seed.oceanbase` | 可选 SQLAlchemy/OceanBase Engine、Session 生命周期、连接池、健康检查与方言能力探测；不提供业务 Model、Repository、SQL 或 migration |

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

Kernel 不依赖 Pydantic 以外框架；adapter 可依赖 contract，反向禁止。Context 使用不可变 request scope，异步任务显式序列化允许字段，避免 contextvar 泄漏到后台任务。发布面按最小可选 extras 拆分为 `core`、`fastapi`、`security`、`otel`、`redis`、`oceanbase`；消费者只安装实际使用的 extra，禁止基础安装隐式拉入所有中间件驱动。

### 3.2 契约细则

- Error：`domain/code/retryable/user_message/recovery/correlation_id/details_ref`，details 默认不跨边界。
- Event：`eventId/eventType/schemaVersion/occurredAt/tenantId/actor/correlationId/payload`；未知字段策略和 upcaster 明确。
- Audit：actor/action/target/reason/before-after digest/result/risk；高风险审计失败默认阻止提交。
- Retry：仅对声明幂等的操作和白名单错误；full jitter、deadline budget、Retry-After；未知写结果转查询对账。
- State primitive：expected version CAS、允许迁移、终态；业务枚举只在所有者工程。
- Access scope：固定输入为 capability decision、direct/effective Own predicate、Creator/User membership 与版本，输出 allow/deny、scope 和来源；不包含 ManagerGroup 图、PermissionPolicy 或业务实体读取。Mud 负责 capability/effective Own，资源所有者负责本地 AccessMetadata 和最终调用。

### 3.3 版本和兼容

公开 surface 维护 API stability matrix。弃用先告警一个 minor，破坏变化升 major；事件 schema 与 wheel 解耦，消费者 migration manifest 记录最早/最晚版本。Seed 自身不提供旧业务 alias；兼容窗口结束删除 adapter。

## 4. Assignment 驱动的迭代与发布

Seed 不规划脱离真实需求的产品 Sprint。业务工程发现公共基础缺口时，从自己的 Story/Task 派生最小 `dependency` Assignment，写入 Seed `docs/assignments/inbox/`；输入只描述目标行为、无业务语义边界和消费者验收，不猜测版本、不规定 Seed 内部实现。Seed 在下一次主动规划时接受、调整、延期或拒绝，并自主映射本地 Story/Sprint：

```text
consumer Story/Task → dependency Assignment (pending)
  → Seed 主动规划并映射本地 Story/Sprint (planned)
  → Seed 最小契约/实现与纯单元/adapter 测试
  → 一次构建并签名最终 version 的不可变 wheel/digest
  → 发布绑定 Assignment 的 dependency-package Delivery (delivered)
  → 消费工程读取精确 version + SHA-256，更新锁文件并完成自身 Test
```

Assignment 是唯一跨工程需求输入，不再维护静态消费者映射表；原 24 条依赖边已按来源 Story 无损迁移为 12 个 Assignment，逐条映射见 [docs/assignments/MIGRATION.md](docs/assignments/MIGRATION.md)。迁移后发现的 `SEED-013/seed.secrets` 输入以独立 pending Assignment 补充，不回写历史迁移，也不把已有源码冒充为已接受/已交付。维护、安全修复和构建工具升级可以来自具体消费者 Assignment，也可以由 Seed 维护者创建本地 Maintenance Story；后者必须说明受影响的已知消费者与迁移验证。跨仓库变更遵循 add → migrate consumers → remove：先发布可兼容的新能力，再由各消费者通过独立 Assignment/Story 迁移，最后在明确版本删除旧入口；不得长期双实现或用 path/Git 依赖代替正式制品。

每个 Assignment 交付必须具备：有效且绑定输入摘要的 accepted Response、来源引用、本地 Story/Sprint、完整 Git object ID、最小公开 API、纯单元/adapter 测试、适用的消费者契约证据、SemVer 与兼容矩阵、升级/回滚说明，以及含 package/version/SHA-256/签名/SBOM/provenance 的 `dependency-package` Delivery。同一 Delivery ID 不得覆盖换包；Delivery 只有经项目配置的真实 verifier 校验签名、SBOM 和 Build Once、生成绑定 Delivery 与全部 Artifact 身份的受管 receipt 后才能成为 `delivered`。破坏变更还必须根据包索引与代码搜索登记已知消费者和旧入口删除版本。staged/release 是同一私有包索引中的权限/channel 状态，提升不得重建、重命名或改变 wheel；安装必须校验受信签名与锁文件 SHA-256，并禁止同名公共索引回退以防 dependency confusion。

## 5. 设计与发布

公开 API 经 `seed.*` 稳定入口暴露，Provider 使用 Protocol/ABC 注入；核心层只依赖标准库/Pydantic，FastAPI/OTel 等放可选 extra。包遵循语义化版本，锁定 Python 3.12+，产出 wheel、类型声明、SBOM 和签名。事件 `schemaVersion` 独立于 wheel 版本：生产者先发布可选字段或新版本，消费者验证并迁移，最后按登记版本停止旧事件；重放器在保留期内保留对应 decoder。破坏变更升主版本并附迁移和旧版本删除计划，不提供无限期 alias。

Mud、Stem、Mint、Tea、Iris、Sop 等 Python 后端通过带签名、SBOM、provenance 和类型声明的版本化 wheel 依赖 Seed，在锁文件中固定精确 version + SHA-256。Test/Production 禁止 Git、分支、本地 path 或公共索引回退依赖。Celt、Vine、Sage 不安装、不打包也不消费 Seed 契约制品。

## 6. 质量门槛

pytest、mypy strict、Ruff 强制；Seed 仓库提供契约夹具和最小 FastAPI/消息样例，各真实消费者在自身 CI 运行兼容测试并回报版本矩阵，从而不产生 Seed 对业务工程的反向依赖。Test 样例运行在 K3d/K3s，覆盖配置挂载、Secret、探针、优雅停机和 Trace 传播。

每个 adapter 还需故障注入：Secret 不可用、OTel collector 不可用、SIGTERM 中途、HTTP timeout、重复事件、时钟偏差。日志/异常 snapshot 做 Secret canary 扫描。授权 kernel 由 Mud、Stem、Tea 及后续私有资源所有者在各自 CI 运行同一正反夹具；Seed 不连接这些服务，也不形成反向依赖。

能力成熟度用于 Seed 自主排期而非独立产品路线：S0 kernel/contracts → S1 按需 framework/middleware adapters → S2 reliable client → S3 consumer compatibility kit。每次 Sprint 必须追溯到已接受 Assignment 或明确的本地 Maintenance Story，不建设“大而全基础平台”。
