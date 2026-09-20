# maia-seed

基线：`maia-greenfield-20260920`。旧项目实现和执行数据已归档，当前是待 Review 的新设计输入，没有运行中的新业务实现。

- [架构](ARCHITECTURE.md)
- [用户故事](USER_STORIES.md)
- [上游 Maia 架构](../ARCHITECTURE.md)
- [重建记录与恢复位置](../docs/references/maia-rebaseline-20260920.md)

治理检查：`uv run --project .harness/runtime harness requirements validate`、`uv run --project .harness/runtime harness doc-lint`。Harness 使用 Python 工具运行时，与目标 TS 业务栈分离。当前没有已接受需求；消费者 dependency 到达并接受后才建立新 Story。
