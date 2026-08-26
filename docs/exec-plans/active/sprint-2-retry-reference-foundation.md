# sprint-2-retry-reference-foundation

sprint_type: library-sprint
base_ref: refs/remotes/origin/develop
base_sha: 803d76270922d044229917b67876f693b1ca1148
branch: library/2-retry-reference-foundation

- **目标**：在 maia-seed 提供 provenance-aware retry seal 与通用 retry-reference key-ring/codec，保证 request snapshot 在 provider 后为不可变总操作
- **状态**：active
- **环境就绪**：✅
dependency_session: seed-dep-mud-s2-r01-retry-reference-foundation
request_digest: sha256:6f9cc9d25900fd7a71f9218cd82c6f7388435f131177830c41eb6086dab07874
capability: retry-reference-foundation
- **验收条件**：反射伪造 exact verified type 无法分类为可重试；snapshot 阶段冻结 sealed references，issue 不再读取 key/clock/random/codec；Seed 提供无 Mud/WeCom 语义的 codec/key-ring，Mud 仅保留业务绑定；正反例消费者测试、Delivery、新 wheel 版本/SHA-256/供应链 receipt 与 Mud lock 一致

## 任务

| ID | 类型 | 来源 | 父任务 | 任务描述 | 依赖 | 产出物 | 验收条件 | 状态 |
|---|---|---|---|---|---|---|---|---|
| S2-D01 | library-design | remediation | S2-R01 | 定义 provenance-aware retry seal、通用 retry-reference codec/key-ring、不可变 request snapshot API、兼容策略与消费者矩阵 | - | `docs/tech-docs/sprint-2-retry-reference-foundation.md`；API stability matrix 更新 | 公共 API 不含 Mud/WeCom 语义；反射伪造、snapshot 总操作、key/clock/random/codec 边界与兼容升级规则明确 | done |
| S2-C01 | library-code | remediation | S2-R01 | 修复 verified reference provenance 校验并实现通用 codec/key-ring 与 snapshot 阶段 sealed reference 冻结 | S2-D01 | `src/seed/` 公共 API 与实现；`tests/` 正反例 | 反射伪造 exact type 无法分类；snapshot 后 issue 不读取可变依赖；通用实现不包含消费者语义；静态、类型、单测通过且 0 Critical / 0 Major | done |
| S2-Q01 | library-quality | planned | - | 对最终 Seed 源码提交执行 Library 全量质量评分 | S2-C01 | `docs/test-reports/sprint-2-retry-reference-foundation-quality.md` | `command_groups.precommit` 通过；覆盖率达到阈值；质量分达到 95 | done |
| S2-P01 | library-package | planned | - | 从通过质量门禁且已提交的源码执行一次 Build Once，登记新的不可变 wheel | S2-Q01 | `dist/` wheel；`.harness/state/library-packages/sprint-2-retry-reference-foundation.json` | version 升级、完整 source commit、package state 与 SHA-256 一致；candidate 仅构建一次 | done |
| S2-V01 | library-contract | planned | - | 登记 Build Once candidate 并运行 Mud retry-reference foundation 消费者契约 | S2-P01 | 当前 dependency session 的 consumer evidence | 伪造 seal、不可变 snapshot、codec/key-ring 正反契约针对同一 candidate 通过；破坏性变更已升级 major 或被拒绝 | done |
| S2-L01 | library-delivery | planned | - | 发布绑定当前 session、candidate 与供应链证据的不可变 dependency-package Delivery | S2-V01 | `docs/deliveries/` Delivery；供应链 verification receipt | Delivery 绑定当前 request digest；version/source commit/SHA-256 一致；签名、SBOM、provenance receipt 有效 | done |
| S2-X01 | library-close | planned | - | 在全部 Library 交付门禁通过后归档本 Sprint | S2-L01 | `docs/exec-plans/completed/sprint-2-retry-reference-foundation.md` | 全部前置 Library 任务完成；计划原子归档到 completed | pending |
| S2-R01 | library-pr | planned | - | 通过统一 PR adapter 创建 Library Sprint 合并请求并确认远端门禁 | S2-X01 | PR/MR URL | PR/MR 由 `harness pr-adapter` 创建；远端 CI 与分支保护通过 | pending |
