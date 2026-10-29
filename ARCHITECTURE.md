# Maia Seed 架构

产品职责入口见 [Seed 概览](../docs/product/seed/overview.md)，公共包治理见[技术栈与消费者交付](../docs/architecture/technology-stack.md#51-公共包与消费者交付)，总体归属见[Maia 架构](../ARCHITECTURE.md)。

## 1. 定位

Seed 为实际 TS/Node.js 消费服务提供版本化 npm 技术包，不部署独立进程。边界和验收由真实消费者需求驱动，业务适配保留在消费工程；Celt 不依赖 Seed，Sage/Vine 不引入后端库。

## 2. 包边界

| Seed 可按真实需求提供 | 仍由消费服务维护或执行 |
|---|---|
| 配置加载/校验、上下文、ID/时钟机制 | 业务配置、默认值、根策略和实体身份 |
| 错误/事件 envelope、序列化、契约测试工具 | 领域错误码、事件类型、业务状态及兼容政策 |
| Secret/加密端口、脱敏、日志/Trace 初始化 | 凭据权限、分类与审计语义 |
| DB/Redis 生命周期、健康和技术故障映射 | Repository、SQL、Schema、业务 key/TTL 及幂等 |
| 已接受需求的纯授权算法及一致性夹具 | Mud 的 AccessContext，资源服务的 AccessMetadata/附属映射及最终授权 |

Seed 不读业务表、不调用 Mud/Stem、不反向依赖消费者，也不运行 Worker/业务 handler 或队列台账。队列使用[原生 BullMQ 边界](../docs/architecture/async-jobs.md#1-职责与整体处理链路)，多个真实消费者确有重复技术需要时才提供薄适配，不预建 mq-client/Broker。服务 API 客户端由真实所有者治理，Iris 模型和 checkpoint 适配留在 Iris。

## 3. 当前契约

### 3.1 maia-snowflake

`maia-snowflake`（`seed.snowflake`）是本地 ID SDK，提供生成、编解码、校验及并发/回拨/重启保护，不依赖在线分配服务。格式、ID 语义及跨语言传输只引用[Snowflake 契约](../docs/architecture/data-architecture.md#3-snowflake-生成与传输契约)，workerId 物理分配和安全复用见[部署设计](../docs/DEPLOYMENT.md)。SDK 内部算法、时钟/重启策略和故障向量随实际实现验证，不复制 epoch/位布局为另一份规范。

### 3.2 access-scope-kernel.v1

纯算法输入为 Owner、使用范围元素及 Mud 发布的 AccessContext，输出单条 Own/Use/拒绝与原因，以及可下推集合过滤条件。输入含根边界与版本；缺失上下文、未知版本或跨根拒绝。具体谓词只以[权限模型](../docs/product/constraints/permission-model.md#217-判定契约)和[授权上下文与裁决](../docs/architecture/public-data-contracts.md#11-授权上下文与裁决)为准。

kernel 不读取成员关系、不保存树路径/上级 ID、不处理附属映射、业务依赖或能力兼容性。输入形状/纯函数 API、集合过滤语义和一致性夹具由实际消费者契约固定；Mud 发布身份事实，各资源服务在业务用例中执行最终授权判定，不能将算法包变成在线鉴权服务。

### 3.3 其他技术适配

实际需要 DB 适配时仅治理 Drizzle/mysql2 连接生命周期和技术错误；示例/helper/插件同样遵守[数据库及 Drizzle 边界](../docs/architecture/data-architecture.md#4-drizzle-与-tidb-兼容边界)，不得包装被禁能力绕过总仓约束。其他技术能力也须有 capability ID、消费者、输入输出、失败语义及兼容测试，不以公共包名预建全套模块。

## 4. 制品与消费者验证

运行时、编译器、依赖和包管理精确版本继承[技术栈基线](../docs/architecture/technology-stack.md)，包的 engines/peer、ESM/CJS 及兼容范围按实际消费者声明；按必要功能拆包，避免无关消费者加载 DB/加密依赖。

制品绑定包名、版本、完整性摘要、源码提交、签名及 SBOM/provenance；消费方验证组织信任根并锁定制品，Test/Production 不用浮动标签、Git/path 依赖或同版本重打包。制品治理只在总仓维护，Seed 提供真实包契约及其可复验消费者证据。

验证覆盖独立纯函数/失败语义、消费者兼容及实际采用机制；Snowflake 的大整数、回拨/重启与并发向量，kernel 的根隔离、成员/继承命中和集合谓词一致性分别跟随包交付，不替代消费服务的业务授权验收。公共抽象的新增遵守[架构取舍](../ARCHITECTURE.md#12-架构取舍原则)，运行资源与基础设施配置仅引用部署文档。
