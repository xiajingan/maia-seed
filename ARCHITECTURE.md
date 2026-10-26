# Maia Seed 架构

上游：[Maia 架构](../ARCHITECTURE.md)、[技术栈与版本](../docs/architecture/technology-stack.md)、[产品需求](../docs/product/seed/overview.md)。

## 1. 定位

Seed 是供 Maia TS/Node.js 业务服务按需消费的公共技术库，以版本化 npm 制品交付，不部署独立进程。

公共模块由实际消费需求确定边界与验收，业务适配保留在消费工程。

## 2. 边界

| 可以按真实需求提供 | 必须留在消费者/服务 |
|---|---|
| 配置加载与校验、上下文传播、ID/时钟等基础机制 | 业务配置项、默认值、根 Workspace 策略和实体身份 |
| 错误/事件 envelope、序列化和契约测试工具 | 领域错误码、事件类型、状态枚举与兼容政策 |
| Secret/加密端口、脱敏机制、日志/Trace 初始化 | 凭据使用权限、数据分类、审计事件语义 |
| 数据库/Redis 生命周期、健康和技术故障映射 | Repository、SQL、Schema、业务 key/TTL 与幂等策略 |
| 经接受需求定义的纯授权范围算法（`access-scope-kernel.v1`）和一致性夹具 | Mud Workspace 树/Membership 与 AccessContext 的产生和发布；各服务的 Creator/Owner/使用范围事实、附属对象到主对象的映射与最终授权用例 |

队列默认由业务工程直接使用 BullMQ 原生 Queue/Worker，不要求独立 maia-mq。Seed 仅在多个真实消费者需要时提供薄技术适配、生命周期或观测工具，不运行 Worker 服务、不承接业务 handler/队列台账。对象引擎及领域服务也不进入 Seed；真实服务的 API 客户端由服务所有者治理。Seed 不调用 Mud/Stem，不读取业务表，不反向依赖消费工程。

队列消费边界见 [Maia 异步任务架构](../docs/architecture/async-jobs.md)，新增公共抽象按 [架构取舍原则](../ARCHITECTURE.md#12-架构取舍原则) 证明减少整体维护成本，不预建 mq-client 或通用 Broker。Iris 的 DeepAgents、模型与 checkpoint 适配归 Iris，不因多个工程使用 TS 就移入 Seed。资源、节点与部署要求统一引用 [Maia 部署设计](../docs/DEPLOYMENT.md)，技术方案不复制部署内容。

Celt 保留 Python 客户端边界，不依赖 Seed。Sage/Vine 使用服务契约或必要前端包，不因同为 TS 被迫引入 Node 后端库。

## 3. 包与契约

Maia 已选择 TiDB、Drizzle、MySQL 8.0 兼容子集与全局 Snowflake。Seed 若提供数据库适配，只治理 Drizzle/mysql2 连接生命周期和技术错误；业务 Schema、查询、规则和分析口径留在所属服务。不可将存储过程、数据库业务触发器、复杂 JSON/全文或 TiDB 专有 SQL 包装成“通用能力”绕过上游原则。

适用的运行时、编译器和数据库组件版本继承 [Maia 已确定组件版本](../docs/architecture/technology-stack.md#2-组件版本基线)。数据库适配及示例遵守 [Drizzle 使用边界](../docs/architecture/data-architecture.md#4-drizzle-与-tidb-兼容边界)：禁止 Relational Query API 的关系加载 `with`，不得在 helper/插件中恢复同类自动查询和嵌套组装。消费者仍可使用显式 JOIN；SQL CTE 的 `WITH` 不属于该禁令。

包管理、Schema 技术适配、测试与构建工具均继承上游技术栈版本基线的精确版本，遵守 [Maia 工程默认值与决策边界](../docs/architecture/technology-stack.md#4-工程默认值与决策边界)：使用固定 pnpm 版本并提交锁文件，只引入能力实际需要的依赖。

**`maia-snowflake` 是 Seed 提供的本地 ID SDK（`seed.snowflake`）。** 统一实现生成、编解码、校验及并发/回拨/重启保护，以版本化 TS/npm 制品交付。格式及业务语义继承 [Maia Snowflake v1](../docs/architecture/data-architecture.md#3-snowflake-生成与传输契约)，所有 TS 服务包括 Mud 均直接复用；库不调用 Mud 或依赖在线分配服务。workerId 由部署配置保证唯一分配与安全复用，详见 [部署文档](../docs/DEPLOYMENT.md)。算法细节和故障测试留在 SDK 实现设计中，Celt 按平台协议无损传递 ID。

**`access-scope-kernel.v1` 是纯授权范围算法**，语义以 [Maia §2.1 权限模型](../docs/product/constraints/permission-model.md#21-权限模型) 与 [Maia 架构 §3.2](../ARCHITECTURE.md#32-权限) 为准，由实际消费者需求驱动交付：

| 输入 | 内容 |
|---|---|
| Owner | `owner_workspace_id`（W）与可空的 `owner_user_id`（U，表示个人节点 W/U） |
| 使用范围元素 | 指定 User，或指定 Workspace（仅本级 / 含下级）；为空表示仅 Owner |
| AccessContext | 由 Mud 发布：请求主体的直接成员关系及其上级链、有效 `manager` 集合 `{workspaceId, source(direct\|inherited), viaWorkspaceId}`、version |

- **Own**：`owner_workspace_id` ∈ 有效 `manager` 集合，或（`owner_user_id` = 本人，且 `owner_workspace_id` ∈ 本人直接成员关系）。
- **Use**：Own，或使用范围元素命中本人、本人直接所属的 Workspace，或上级链中选择“含下级”的 Workspace。
- 输出单条裁决（Own / Use / 拒绝及原因）与可下推的集合过滤条件；AccessContext 缺失、版本未知或根 Workspace 不一致时拒绝。
- 不读取成员关系、不调用 Mud、不保存路径或上级 ID，不处理附属对象映射、依赖资源校验或能力兼容性；这些留在消费服务。

数据库与 ID 的完整约束见 [Maia 数据库及 ID 原则](../docs/architecture/data-architecture.md#2-数据库五条硬约束)。

采用已选 TypeScript strict / Node.js 基线；包名、模块拆分、ESM/CJS、面向已选 Node 基线的 engines/peer 兼容声明和测试工具在包契约中声明，不另选运行时或编译器版本。按必要功能拆分，避免无关消费者加载数据库/加密等依赖。

公开接口须可独立测试、版本化且不含消费者业务语义。每个公共能力有 capability ID、消费者、输入/输出和失败语义、一致性/兼容测试。只有存在需求且技术边界稳定才进入公共包；单消费者的业务适配留在消费工程。

## 4. 制品与依赖契约

公共包以不可变 npm 制品交付，绑定包名、精确版本、完整性摘要、源码提交、签名与 SBOM/provenance。消费工程验证组织信任根，锁定版本和制品完整性，并执行消费者契约测试；Test/Production 不使用浮动标签、Git/path 依赖或同版本重打包。
