# maia-seed

按真实消费者需求交付的公共技术包，不运行独立业务服务。

技术栈：TypeScript / Node.js / npm library；具体版本见[技术栈基线](../docs/architecture/technology-stack.md)。

US-001 工程依赖已实现 `maia-snowflake` SDK；本工程不运行独立服务。业务验收与整体迭代阶段以[总仓状态](../AGENTS.md#当前状态)为准。

`maia-snowflake` 提供本地生成、编解码、输入校验、独占状态与重启防重，公开入口及恢复限制见[SDK 设计](docs/tech/snowflake.md)与[包使用说明](packages/maia-snowflake/README.md)。本地 tarball 供 Mud 隔离消费验证；组织信任根、Test/Prod 发布及消费者业务验收仍须分别验证。

## 检查与打包

使用基线 Node/pnpm，运行 `pnpm install --frozen-lockfile`、`pnpm check`；检查覆盖 lint、strict 类型、公开行为测试与包构建。测试用例入口为 [TC-SEED-001](docs/test-cases/TC-SEED-001.md)。

打包：`pnpm --dir packages/maia-snowflake pack --pack-destination ../../artifacts`。制品不入 Git；一次生成后记录 sha512，不同内容不得使用同一版本重新交付。

## 阅读入口

- [本工程架构](ARCHITECTURE.md)：结构、数据/模块职责及边界。
- [工程职责与需求](../docs/product/seed/overview.md)：先看当前采用范围，再按[主故事索引](../docs/product/index.md)与[故事地图](../docs/product/story-map.md)选取业务。
- [公共规则](../PROJECT_RULES.md)与[工程规则](PROJECT_RULES.md)：实施及检查要求；[AGENTS](AGENTS.md)提供任务导航。
- [总仓架构分篇](../ARCHITECTURE.md#2-架构分篇索引)和[部署设计](../docs/DEPLOYMENT.md)：跨工程契约、运行及发布配置。

`docs/tech/` 保存当前模块设计，`docs/test-cases/` 保存本工程用例；普通文档维护按总仓规则检查并以 Git 追溯，明确启动的业务或修复流程才维护必要过程记录。
