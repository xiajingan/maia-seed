# `seed.reference-keyed-digest.v1` 公共包技术方案

状态：`draft`（SD3-D01）；当前发布基线：`maia-seed==0.2.0`；目标版本：`0.3.0`。

## 1. 能力与所有权

- capability ID：`seed.reference-keyed-digest.v1`；Provider/owner：`maia-seed` 的 `seed.crypto`。
- 输入绑定 session 为 `seed-dep-mud-s3-c02-reference-keyed-digest`，request digest 为 `sha256:2f66a55e0e5e42e992f9773c044b49c60fc5196dc4ff411a63667a44d4ecf3c6`；来源映射为 `maia-mud` / `sprint-3-channel-management-foundation` / `S3-D01`。早期草案 session 名不是绑定身份，不用于交付或证据。
- 追溯 Story：`SEED-005`（可替换 crypto/轮换/零泄漏）、`SEED-010`（不可变 wheel）、`SEED-011`（无业务语义）、`SEED-017`（API 变化治理）、`SEED-018`（Secret canary）、`SEED-023`（跨库升级与回滚）。
- 问题：消费者需对 opaque reference 产生稳定、不可逆、带密钥且用途隔离的公开摘要。无密钥 hash、消费者自制 helper、可逆掩码或前后缀截断均不满足该边界。
- Seed 只接收 opaque exact `bytes` 和通用 `domain`，拥有密钥加载、轮换、摘要算法、framing、验证与安全失败合同。`domain` 的业务含义和 reference 构造归消费者。
- 公共 API、默认 domain 和实现模块明确排除 `Mud`/`WeCom`标签、`Tenant`/`Realm`/`AppInstance` 等业务身份、credential/provider identity、业务用途值、数据库/HTTP/审计映射、Secret resolver scheme、消费者配置和轮换运维默认值。
- 已发布基线为 `0.2.0`，wheel SHA-256 为 `b446794310ff1b94cb89735003454b72f83fc03cc85e9459ae4618db51f7fae5`，Delivery 为 `maia-seed.retry-reference-foundation.0.2.0.b4467943`；本次是 additive minor，规划为 `0.3.0`。

## 2. 公共契约

### 2.1 稳定 surface

`seed.crypto` 是唯一公共入口。`__all__` 保留原有 `CryptoContractError`, `KeyProvider`, `AeadKeyRing`, `AeadCipher`, `load_aead_key_ring`, `create_aead_cipher` 六个符号的名称和顺序，并在末尾 additive 新增下表五个符号：

| 符号 | 稳定 shape |
|---|---|
| `ReferenceDigestKeyRing` | 不可伪造、immutable/redacted 的摘要专用 key view；不是 `AeadKeyRing` |
| `ReferenceDigester` | 不可伪造、immutable/redacted；`digest(reference: bytes, *, domain: str) -> str`；`matches(reference: bytes, candidate: object, *, domain: str) -> bool` |
| `ReferenceDigestContractError` | `ValueError`；有限 `reason`；异常正文只等于 reason |
| `load_reference_digest_key_ring` | `(provider: KeyProvider, *, active_key_id: str, previous_key_ids: tuple[str, ...] = ()) -> ReferenceDigestKeyRing` |
| `create_reference_digester` | `(ring: ReferenceDigestKeyRing) -> ReferenceDigester` |

复用既有 `KeyProvider.load(key_id: str) -> bytes` Protocol，但摘要 ring/state 与 AEAD ring/state 完全独立；不得传入 `AeadKeyRing`、隐式共享 AEAD key material，或从一类 ring 派生另一类。新增类不公开普通 constructor，禁止 subclass/copy/deepcopy/pickle。

### 2.2 算法、frame 与输入

- 算法固定为 HMAC-SHA-256。wire frame 固定为 `rkd1.<key_id>.<unpadded-base64url-mac>`，MAC 为 32 bytes，base64url 段固定 43 字符。
- canonical MAC input 固定为 `b"seed.reference-keyed-digest.v1\x00" || u16be(len(domain_utf8)) || domain_utf8 || u32be(len(reference)) || reference`。长度字段使用网络字节序，禁止裸拼接。
- `type(domain) is str`，且必须完整匹配 `^[A-Za-z0-9][A-Za-z0-9._:/-]{0,63}$`；无默认 domain。`type(reference) is bytes`，长度 `1..4096`。
- key ID 完整匹配 `^[A-Za-z0-9._-]{1,64}$`。`previous_key_ids` 必须是 exact tuple；恰一个 active、最多 8 个不重复 previous，active 不得出现在 previous。
- Provider 的每份 material 必须是 exact 32-byte `bytes`，load 时立即复制。同一 key ID 不得替换 material；轮换必须使用新 ID 和新 material。

### 2.3 可观察行为与失败模型

- 相同 key/domain/reference 的 `digest` 确定性相同；改变 domain、reference 或 key 中任一项都形成隔离输出。新 frame 只使用 active key。
- `matches` 先严格解析 frame，再按 frame key ID 仅选择 active/previous 中的对应 key，使用 `hmac.compare_digest` 常量时间比较。malformed、tamper、unknown/retired/wrong key、wrong domain/reference、超限或任何错误类型统一返回 exact `False`，不泄漏差异；验证路径不抛 raw/crypto/provider 异常。
- `ReferenceDigestContractError.reason` 精确为 `Literal["invalid_key_ring", "key_provider_contract_fault", "invalid_digester", "invalid_domain", "invalid_reference"]`。正文只等于 reason，不含 key/reference/material 或 provider exception。
- ring 与 digester 的 repr 分别固定为 `ReferenceDigestKeyRing(<redacted>)` 和 `ReferenceDigester(<redacted>)`。不公开 material、provider、内部 mapping、中间 canonical bytes 或原 reference，digester 不保留调用时的 domain/reference/canonical bytes；日志、异常和测试证据只允许安全标识和摘要 frame。

| Public 入口 | 成功 | 唯一失败行为 |
|---|---|---|
| `load_reference_digest_key_ring(...)` | 专用 immutable ring | ID/tuple/数量/重复/material 长度错误 → `invalid_key_ring`；provider 异常或非 exact bytes → `key_provider_contract_fault` |
| `create_reference_digester(ring)` | immutable digester | 非当前完整专用 ring、fake 或 AEAD ring → `invalid_digester` |
| `ReferenceDigester.digest(reference, domain=...)` | `rkd1` frame | domain type/charset/length → `invalid_domain`；reference type/length → `invalid_reference` |
| `ReferenceDigester.matches(reference, candidate, domain=...)` | 仅合法且匹配时 exact `True` | 任何其他情形 exact `False`，不抛异常 |

每个公开 reason 只有上表的可观察来源。内部模块不是公共入口。既有 `CryptoContractError` reason、六个 `seed.crypto` 符号的 signature、AEAD `ac1` frame 和所有合法/失败行为逐字不变。

## 3. 兼容策略

- `0.2.0` wheel/SHA/Delivery 是不可变基线。`0.3.0` 仅 additive 新增上述五个 facade 符号；原六个 crypto 符号、AEAD wire/reason 行为不变，不要求消费者同步切换。
- 本轮无 deprecated symbol。未来兼容扩展走 minor，修复走 patch；合法 public signature/reason/frame 的破坏变化必须升 major。
- 弃用先发标准 `DeprecationWarning` 并至少保留一个完整 minor。删除前必须登记已知消费者、迁移状态与最早 removal major；禁止无限 alias 或双实现。
- 新 composition 用新 active key 签发；previous 只验证旧 frame。保留窗口由消费者/运维决定，Seed 不内置 TTL。key 退休后其旧 frame 安全返回 `False`。
- 升级遵循 add → migrate → remove。消费者先保存声明/锁文件/adapter 完整 snapshot，再锁定同一 `0.3.0` wheel + SHA 运行合同。失败时恢复上一不可变 `0.2.0` 及精确 SHA 和 snapshot；不覆盖版本、不删远端制品，不使用 Git/path/latest、公共索引回退或 floating lock。

## 4. 实现结构

```text
seed.crypto facade
  └─> package-private digest models/state, validation, framing/HMAC
         └─> stdlib hmac/hashlib + 既有通用 key-loading/validation 原语
```

- `seed.crypto` 只导出第 2 章公共 API。digest model/key state、canonical framing/HMAC 和 validation 分离在 package-private 模块，消费者不得 import。
- 依赖只允许 digest facade/internal 指向标准库与既有通用原语；不反向依赖 `retry_reference`、消费者、Web/DB 框架，不新增第三方依赖。
- 后续 code 任务预计只影响 `src/seed/crypto.py`、新建 `src/seed/_crypto_digest*.py`、共享 validation/model 的最小 additive 调整、`tests/unit/test_crypto.py`、`tests/architecture/test_boundaries.py`、`tests/security/test_secret_canary.py` 和类型检查 fixture；本设计任务不修改它们。
- 后续实现必须证明：public surface/signature/reason；constructor/reflection fake/copy/pickle/subclass 失败；确定性和域分离；active/previous/retired；tamper/wrong key；strict type/limits；并发只读；repr/error/log/trace/fixture canary；AEAD `0.2.0` 回归；无业务词 architecture scan。

## 5. 消费者矩阵

| 消费者 | 使用入口 | 精确环境 | 强制契约命令 |
|---|---|---|---|
| `maia-mud` | 消费者自有 adapter 将两个业务用途映射为不同 domain，仅传 opaque reference；本方案不固化 domain 值或字段语义 | `/Users/ws/space/git/mai/maia/maia-mud/.harness/worktrees/sprint-3-channel-management-foundation`；`seed-dep-mud-s3-c02-reference-keyed-digest` / `S3-D01` | `seed_reference_digest_contract = ["uv", "run", "python", "scripts/verify_seed_reference_digest_contract.py"]` |

该命令已在消费者 `config/harness.yml` 的 `dependencies.providers.maia-seed.capabilities.seed.reference-keyed-digest.v1.consumer_contract_commands` 登记。当前脚本尚未创建；命令登记完整，但契约执行前必须补齐。缺脚本、缺 candidate、非零、skip/xfail、origin/hash/version 不一致均 fail-closed，本阶段不声明已通过。

消费者合同最低 case：

- 校验精确 candidate wheel origin/version/SHA，不允许混合 module origin。
- 在两个消费者自有 domain 中验证确定性与相互隔离，但证据不固化其值或含义。
- 验证 active/previous rotation、tamper、wrong/retired key；原 reference/key material 不得进入对外 API/DB/log/error/evidence。
- 消费者不存在本地 HMAC/hash helper；合同只测试公开 API，不读 Provider source 或 private modules。

## 6. 交付方案

1. package 固定为 `maia-seed`，目标版本 `0.3.0`。Build Once 只在质量门禁通过、source-clean 且 commit 身份一致的源码上原样运行 Provider 登记的 `package_build = ["uv", "build"]` 一次。
2. 后续顺序为 design → code → quality → package → consumer contract → delivery。本设计阶段不预报 candidate 身份或合同 PASS。
3. Delivery 必须绑定实际 session/request digest、完整 source commit、唯一 wheel version/SHA-256、quality evidence、签名、SBOM、provenance 与真实 verifier receipt。staged/release 只改变权限/channel，不重建或改名。
4. consumer contract 必须针对同一 Build Once candidate。消费者更新声明和锁文件后，version/hash 须精确一致；禁止 source/editable/path/Git/latest、公共索引回退或混合 module origin。
5. 回退只恢复上一不可变 `0.2.0` wheel/SHA 与消费者完整 snapshot，不删除 `0.3.0` artifact，不改写同版本。
