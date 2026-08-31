# develop 分支保护审计

## 背景

`maia-seed` PR #3 在 2026-08-31 通过远端 CI 并合并，但合并前没有独立批准。该历史事实不可回写，本报告将其记录为一次显式治理例外，不将后续修复倒推为当时已经满足审批门禁。

## 当前保护基线

`develop` 的远端保护与 `.github/branch-protection.json` 对齐：

- 变更必须通过 Pull Request 合入；
- 至少需要 1 个非作者批准，新提交会使旧批准失效；
- 管理员和具备 bypass 权限的角色同样受保护规则约束；
- `L1 Quality`、`Doc Lint`、`PR Format Check` 必须通过，且分支必须基于最新基线；
- 要求线性历史，禁止 force push 和删除分支。

## 验证方法

治理验证 PR 必须先在无批准状态下尝试由 `harness pr-adapter` 合并，并确认远端拒绝；随后由独立 reviewer 对同一 head 提交批准，在必需检查全绿后再次通过 adapter squash 合并。PR URL、head SHA、拒绝输出、review 和最终 `develop` 到达证据归档到对应 Harness task attempt。

## 结论

PR #3 的历史缺口由仓库负责人明确接受为一次例外。自本规则生效后，相关 PR 必须经过人工 Review；验证 PR 本身也不豁免。
