# 项目规则

> 基线：`maia-greenfield-20260920`；更新：2026-09-20。架构与需求以 [ARCHITECTURE.md](ARCHITECTURE.md)、[USER_STORIES.md](USER_STORIES.md) 为准。

## 当前阶段

重建输入、Review 和确认先于实现；当前无 active Sprint、可部署业务制品或已接受新 Delivery。旧实现与执行状态不能用于跳过新基线门禁。不要创建空 package.json、占位 API 或总是成功的测试来消除缺失能力诊断。

## 文档边界

架构与技术方案只定义技术选型、领域/数据所有权、接口协议、安全、一致性与失败行为。TiDB、SeaweedFS、BullMQ/Redis 等资源、节点、拓扑、网络入口、PV、镜像/Chart 和部署要求只维护在 [Maia 部署文档](../docs/DEPLOYMENT.md) 及其环境手册；技术方案引用入口，不复制部署内容。Snowflake 生成器编号属于算法契约，其物理实例映射才属于部署。待验证项由工程完成，不默认转成用户逐项选型或批准。

## 实现边界

- TS strict / Node.js 为服务与公共包主栈，HTTP 使用 Fastify。Celt 与 Harness/开发脚本的 Python 不构成业务服务例外扩张。
- 边界执行运行时 Schema 校验；使用 unknown 收窄输入，避免无约束 any；函数/类型命名明确，模块按职责拆分。
- 数据归属、租户和授权检查集中于用例；禁止跨服务读表、复制 Provider 实现或让前端提交授权事实。
- 领域不耦合传输/数据库引擎；SQL 参数化，Schema 只经所属服务的版本化迁移。
- 外部调用、消息与异步重试明确幂等及结果未知语义；禁止无限重试和吞掉异常冒充成功。
- 结构化日志关联请求与业务 ID，凭据与敏感原文不明文进入日志、事件或模型上下文。
- Seed 按真实 dependency 交付 TS 包；MQ/Storage 是独立服务，所属服务治理自己的契约客户端。

## 数据库与业务 ID

遵守 [Maia 架构 DB-01～05](../ARCHITECTURE.md#22-数据库五条硬约束) 与 Snowflake 契约：TiDB HTAP、Drizzle MySQL 方言、MySQL 8.0 兼容子集；业务逻辑在代码，不使用存储过程/数据库业务编程、复杂 JSON 查询或全文索引。业务主键/引用为 Snowflake BIGINT，API/事件/队列用十进制字符串，禁止 JS number 转换和数据库自增代替。

使用已固定的 [Snowflake v1 格式及 SDK 契约](../ARCHITECTURE.md#23-snowflake-生成与传输契约)，不得按工程、租户或业务修改 epoch/位布局；唯一公共实现归 Seed 的 maia-snowflake（seed.snowflake），所有 TS 服务锁定消费，不各自复制算法；发号不依赖在线服务，workerId 唯一分配与安全复用由部署配置保障。

Review 覆盖 ORM 生成 SQL、迁移与必要手写 SQL，以及 ID 精度、全局节点分配和回拨/重启语义。JSON 载荷存储与标准关系查询不等同于获准使用复杂 JSON 函数；ORM 参数化也不等同于语法或执行语义已验证。

按 [Maia Drizzle 使用边界](../ARCHITECTURE.md#24-drizzle-与-tidb-兼容边界)，禁止 Relational Query API 的关系加载 `with`（含 `findMany`、`findFirst` 及封装），技术适配与示例不得绕过。使用 Drizzle 显式查询构建，普通 JOIN 允许；符合兼容规则的 SQL CTE `WITH` / `db.$with()` / `db.with()` 不在此禁令内。Review 必须辨别 API 语义，不以关键词扫描宣称已完成自动检查。

## 验证与交付

构建与契约验收沿用 [Maia 已确定组件版本](../ARCHITECTURE.md#25-已确定的组件版本基线)，只引入能力实际需要的依赖；包的 peer/engines 范围由已接受的消费者契约确定。安全修复与受控升级按架构更新，不能把锁定解释为长期不升级。

业务实现建立后，在 `config/harness.yml` 登记真实 lint/typecheck、行为测试、构建及相关数据库/契约命令。覆盖授权拒绝、跨租户隔离、恢复与外部副作用；文档检查不能替代业务验收。Node、npm 依赖、OCI 镜像和引擎版本必须锁定，升级有消费者验证和恢复证据。

文档重设当前只运行需求结构、链接、配置及 diff 检查。性能/容量/覆盖阈值由新设计的风险和验收决定，不继承旧测试报告中的达标结论。
