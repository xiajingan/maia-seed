# CONSUMERS v1 → Assignment v2 迁移

`CONSUMERS.yaml` 的 24 条单边记录已按 `(consumer_repo, consumer_story)` 合并为 12 个不可变 `dependency` Assignment，保存在 `docs/assignments/inbox/`。合并只改变输入载体，不改变原 `seed_task`、surface、extras、consumer test、change type、升级、回滚或删除版本语义。

迁移原则：一个消费 Story 对 Seed 的同一次能力请求是一张 Assignment；原每条依赖边完整保留在 `requested_capabilities[]`，字段为 `legacy_record`、`seed_task`、`surface`、`extras`、`consumer_test`、`change_type`、`upgrade`、`rollback`、`removal_version`，便于逐条审计。原记录均为 additive 且没有预定删除版本，因此 `removal_version` 显式为 `null`；所有记录当前均未交付，所以不伪造 version、SHA-256 或 Delivery。后续 Seed 主动规划时接受/拒绝，完成后发布绑定 Assignment digest 的真实 `dependency-package` Delivery。

| Assignment | 来源 | 原记录数 |
|---|---|---:|
| `seed-dep-mud-p0-001` | `maia-mud:MUD-P0-001` | 3 |
| `seed-dep-mud-p0-003` | `maia-mud:MUD-P0-003` | 2 |
| `seed-dep-mud-p0-020` | `maia-mud:MUD-P0-020` | 1 |
| `seed-dep-mud-p0-051` | `maia-mud:MUD-P0-051` | 1 |
| `seed-dep-stem-001` | `maia-stem:STEM-001` | 1 |
| `seed-dep-stem-005` | `maia-stem:STEM-005` | 3 |
| `seed-dep-mint-001` | `maia-mint:MINT-001` | 2 |
| `seed-dep-teaapp-008` | `maia-tea:TEAAPP-008` | 2 |
| `seed-dep-iris-001` | `maia-iris:IRIS-001` | 4 |
| `seed-dep-iris-006` | `maia-iris:IRIS-006` | 2 |
| `seed-dep-sop-001` | `maia-sop:SOP-001` | 2 |
| `seed-dep-sop-004` | `maia-sop:SOP-004` | 1 |

以上 12 张 Assignment 合计且仅承接 24 条原记录。迁移文件保留原 `idempotency_key`；首次经统一分发端口遇到既有 inbox 文件时，Harness 会在目标锁内复算其摘要、扫描并校验同 key 唯一性，再回填本地幂等 receipt，不能用不同 Assignment ID 复用旧 key。`CONSUMERS.yaml` 与其 Schema 在本次迁移中删除，不保留双写兼容层。

迁移完成后发现的真实新增输入不回写上述 24 条历史边。`seed-dep-mud-p0-002-secrets` 是由真实 Secret/APPManager Story `MUD-P0-002` 提出的迁移后 `SEED-013/seed.secrets` Dependency Assignment，使用 `origin: post-consumers-migration` 单独标识；它当前保持 `pending`，不得据此伪造 accepted Response、Sprint 或 Delivery。
