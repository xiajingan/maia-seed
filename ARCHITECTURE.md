# Maia Seed 架构

> 基线：`maia-greenfield-20260920`；2026-09-20 重建，待 Review。上游：[Maia 架构](../ARCHITECTURE.md)、[Maia 需求](../USER_STORIES.md)。当前无新实现、已接受依赖或可消费制品。

## 1. 定位

Seed 是供 Maia TS/Node.js 业务服务按需消费的公共技术库，以版本化 npm 制品交付，不部署独立进程。旧 Python wheel、业务绑定测试、Story、Assignment、Delivery 和执行记录已经退出当前基线；其历史不构成新包范围、版本或兼容义务。

从 Mud 的真实 Story/Task 需求开始，接受具有边界和验收的公共能力，再自主规划 Seed 迭代。不会先翻译旧 Seed 全部模块，也不会因为可能复用而阻塞所有服务。

## 2. 边界

| 可以按真实需求提供 | 必须留在消费者/服务 |
|---|---|
| 配置加载与校验、上下文传播、ID/时钟等基础机制 | 业务配置项、默认值、租户策略和实体身份 |
| 错误/事件 envelope、序列化和契约测试工具 | 领域错误码、事件类型、状态枚举与兼容政策 |
| Secret/加密端口、脱敏机制、日志/Trace 初始化 | 凭据使用权限、数据分类、审计事件语义 |
| 数据库/Redis 生命周期、健康和技术故障映射 | Repository、SQL、Schema/migration、业务 key/TTL 与幂等策略 |
| 经接受需求定义的纯授权范围算法和一致性夹具 | Mud 管理组图/Role/Policy；各服务的 Creator/Owner/User 事实与最终授权用例 |

`maia-mq` 与 `maia-storage` 是独立服务，不是 Seed Provider 进程。服务 API 的薄客户端/Schema 由服务所有者治理；不把 BullMQ worker、对象引擎或领域服务塞入 Seed。Seed 不调用 Mud/Stem，不读取业务表，不反向依赖消费工程。

MQ 客户端继承上游已定的 HTTPS 批量发布/长轮询消费协议，由 MQ 所有者发布；Iris 的 DeepAgents、模型与 checkpoint 适配归 Iris，不因多个工程使用 TS 就移入 Seed。资源、节点与部署要求统一引用 [Maia 部署设计](../docs/DEPLOYMENT.md)，技术方案不复制部署内容。

Celt 保留 Python 客户端边界，不依赖 Seed。Sage/Vine 使用服务契约或必要前端包，不因同为 TS 被迫引入 Node 后端库。

## 3. 包与契约

Maia 已选择 TiDB、Drizzle、MySQL 8.0 兼容子集与全局 Snowflake。Seed 若提供数据库适配，只治理 Drizzle/mysql2 连接生命周期和技术错误；业务 Schema、查询、迁移、规则和分析口径留在所属服务。不可将存储过程、数据库业务触发器、复杂 JSON/全文或 TiDB 专有 SQL 包装成“通用能力”绕过上游原则。

适用的运行时、编译器和数据库组件版本继承 [Maia 已确定组件版本](../ARCHITECTURE.md#25-已确定的组件版本基线)。数据库适配及示例遵守 [Drizzle 使用边界](../ARCHITECTURE.md#24-drizzle-与-tidb-兼容边界)：禁止 Relational Query API 的关系加载 `with`，不得在 helper/插件中恢复同类自动查询和嵌套组装。消费者仍可使用显式 JOIN；SQL CTE 的 `WITH` 不属于该禁令。

包管理、Schema 技术适配、测试与构建工具均继承上游 §2.5 的精确版本，遵守 [Maia 工程默认值与决策边界](../ARCHITECTURE.md#26-工程默认值与决策边界)：首个真实包初始化时使用固定 pnpm 版本并提交锁文件，只引入能力实际需要的依赖；工程负责落实和验证，不推迟选版，无需用户逐项指定。

**`maia-snowflake` 是 Seed 提供的本地 ID SDK（`seed.snowflake`）。** 统一实现生成、编解码、校验及并发/回拨/重启保护，以版本化 TS/npm 制品交付。格式及业务语义继承 [Maia Snowflake v1](../ARCHITECTURE.md#23-snowflake-生成与传输契约)，所有 TS 服务包括 Mud 均直接复用；库不调用 Mud 或依赖在线分配服务。workerId 由部署配置保证唯一分配与安全复用，详见 [部署文档](../docs/DEPLOYMENT.md)。算法细节和故障测试留在 SDK 实现设计中，Celt 按平台协议无损传递 ID。

Snowflake 的公共库归属已经确定；首个真实 dependency 落实公开接口、消费者验收和交付版本，不再作为是否抽取的候选。当前未生成执行 Assignment 或可消费制品；完整规则见 [Maia 数据库及 ID 原则](../ARCHITECTURE.md#22-数据库五条硬约束)。

采用已选 TypeScript strict / Node.js 基线；包名、模块拆分、ESM/CJS、面向已选 Node 基线的 engines/peer 兼容声明和测试工具在首个已接受依赖中固定，不另选运行时或编译器版本。按必要功能拆分，避免无关消费者加载数据库/加密等依赖；未交付能力不提供空 API 冒充契约。

公开接口须可独立测试、版本化且不含消费者业务语义。每个已接受能力有 capability ID、消费者、输入/输出和失败语义、一致性/兼容测试、升级/移除条件。只有存在需求且技术边界稳定才进入公共包；单消费者的业务适配留在消费工程。

## 4. 交付链

消费 Story/Task 发现缺口 → dependency Assignment → Seed 接受或有理由拒绝 → 新 Seed Story/Sprint → 实现和 Review → Build Once npm 制品 → Delivery → 消费工程锁定及验收。

Assignment 不预填未产生的版本，不以创建 Assignment 代替接受。Delivery 绑定来源、包名、精确版本、摘要/完整性、源码提交、签名、SBOM/provenance 和消费者验证条件。验证组织真实信任根；配置缺失时不得自动宣称通过。开发联调可以有受控候选，Test/Production 不使用浮动标签、Git/path 依赖或重打包同版本。

破坏性变更采用 add → migrate consumers → remove，记录已知消费者、兼容矩阵、回滚与删除版本。npm 发布机制和当前 Harness 交付验证需在首个真实迭代适配；现有 Python 工具仍是治理运行时，不是可用的新 TS 供应链证明。

## 5. 当前需求与启动条件

[USER_STORIES.md](USER_STORIES.md) 的旧 23 个预置故事已清除。用户已明确指定 Seed 实现 `maia-snowflake`，这是已确定的公共能力；当前尚无执行中的 dependency 或已交付包。配置、身份上下文、错误、加密、观测及纯权限算法等其他缺口仍按实际消费者需求评估，不据此自动开始 Seed Sprint。

下一次迭代从具体 dependency 的目标行为和消费者测试生成新 Story，再 Review、确认；旧版本号、wheel、签名回执和治理例外不能继承为新包验收。框架源码/Agent/Skill 保留，独立的分支保护治理工作树也保留，不将它当作业务交付记录。
