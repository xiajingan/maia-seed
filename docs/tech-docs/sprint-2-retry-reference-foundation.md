# `retry-reference-foundation` 公共包技术方案

状态：draft（S2-D01）；当前发布基线：`maia-seed==0.1.0`；目标版本：`0.2.0`。

## 1. 能力与所有权

- capability ID：`retry-reference-foundation`；Provider/owner：`maia-seed`。来源 session 为 `seed-dep-mud-s2-r01-retry-reference-foundation`，request digest 为 `sha256:6f9cc9d25900fd7a71f9218cd82c6f7388435f131177830c41eb6086dab07874`。
- 本能力扩展而不重命名 `retry-contract`。Seed 内部所有权分层如下：
  - `seed.crypto`：通用 `KeyProvider`、key material 一次加载/复制、active/previous rotation、AEAD seal/open、nonce allocation 与敏感值约束的唯一真源。
  - `seed.retry_reference`：组合 crypto，拥有 opaque reference framing、namespace/time window、payload verifier adapter、snapshot freeze 与有界 issue。
  - `seed.errors`/`seed.retry`：唯一 verified provenance seal、failure classification、七字段 envelope compose/serialize。
- consumer 只负责 opaque payload/binding 的业务构造与验证，以及产品 DTO/HTTP/观测/业务结果映射、调度策略与性能阈值；Seed 不读取消费工程。
- 明确排除任何消费工程或供应商名称、业务实体/结果类别/URL/error、HTTP schema/status、完成事件、租户/App/Operation 默认值、业务 TTL/重试次数，以及消费工程目录或配置。
- F010 由统一 provenance predicate 关闭；F012 由 freeze 时完成 seal、issue 只读关闭；F013 由 `seed.crypto` 成为通用 crypto 唯一真源关闭。消费者 50×300 秒 soak（F006）和文件拆分（F011）只作为升级后证据。

## 2. 公共契约

### 2.1 Provenance 单一路线

- `verify_retry_reference is verify_details_reference` 仍是唯一 public seal 铸造入口；foundation codec/bound verifier 只返回 exact `bool`，不返回 sealed object、不调用私有 constructor。
- `VerifiedRetryReference is VerifiedDetailsReference` 与 `RetryReferenceVerifier is DetailsReferenceVerifier` identity、三个 failure kind、kind→error mapping、七字段 envelope 和合法 `0.1.0` 输入行为均不变。
- classifier、failure validation、errors compose 复用同一内部 provenance predicate。public exact class 经 `object.__new__`/`object.__setattr__` 填任意 value/seal，以及 fake/copy/pickle/subclass/cross-version/cross-implementation 均一致失败；分类为 `seal_fault`，compose 为 `details_seal_fault`。
- 不把 Python 解释器当安全 sandbox：已主动提取/替换模块私有 provenance、修改 module `__dict__`、使用 debugger 或改写内存的任意代码执行者不在保证范围；该边界不放宽上述 public reflection/fake 负例。

### 2.2 `seed.crypto` 稳定 surface 与 nonce 契约

`seed.crypto.__all__` 精确为：`CryptoContractError`, `KeyProvider`, `AeadKeyRing`, `AeadCipher`, `load_aead_key_ring`, `create_aead_cipher`。

| 符号 | 稳定 shape |
|---|---|
| `KeyProvider` | Protocol：`load(key_id: str) -> bytes`；只按通用 key ID 返回短生命周期材料 |
| `AeadKeyRing` | immutable/redacted；只读 `active_key_id: str`、`previous_key_ids: tuple[str, ...]`；内部持有本 ring generation 的 active key 唯一私有线程安全 nonce allocator/guard，不公开 material 或 allocator |
| `AeadCipher` | immutable/redacted crypto view；引用 ring 的 immutable key view 与共享 allocator/guard；`seal(plaintext: bytes, aad: bytes) -> bytes`；`open(frame: bytes, aad: bytes) -> bytes | None` |
| `load_aead_key_ring` | `(provider: KeyProvider, *, active_key_id: str, previous_key_ids: tuple[str, ...] = ()) -> AeadKeyRing` |
| `create_aead_cipher` | `(ring: AeadKeyRing) -> AeadCipher` |
| `CryptoContractError` | `ValueError`；`reason: Literal["invalid_key_ring", "key_provider_contract_fault", "invalid_cipher", "invalid_crypto_input", "nonce_allocation_fault", "encryption_fault"]`；正文只等于 reason |

- load 一次读取并复制材料；恰一个 active、最多 8 个 previous，ID 唯一且满足 `^[A-Za-z0-9._-]{1,64}$`，material 为 exact `bytes`、恰 32 bytes。ring 不保存 provider、mapping 或调用方 bytes 引用；active 仅 seal，active+previous open。
- wire crypto frame 版本固定为 `ac1.<key_id>.<base64url(nonce || AES-256-GCM-ciphertext)>`；AAD 由调用方提供但不写入 frame；plaintext/AAD 各最大 4096 bytes，frame 最大 12288 bytes。rotation 只创建新 immutable ring/cipher，不原地修改。
- public API 不接受调用方 RNG、nonce、counter、nonce factory 或 time source。production nonce 由 crypto 内部 CSPRNG 与 key-scoped、线程安全 duplicate guard/有界重取生成；耗尽只报 `nonce_allocation_fault`，绝不回退复用。`create_aead_cipher(ring)` 可重复调用，但同一 ring generation、同一 active key 的所有 cipher 必须引用 ring 内同一个 allocator/guard，不得另建、复制或重置；任意 codec/snapshot/并发 seal 均进入同一原子 allocate/check 路径。这是唯一机械不复用保证。
- 公开 `load_aead_key_ring` 即使重复加载相同 key ID/material，也会产生独立 ring generation与独立guard；跨ring、跨进程及重启只承诺内部高质量CSPRNG的概率安全，不宣称共享guard或绝对唯一。轮换运维SHOULD生成全新key ID/material，新composition停止持有/使用旧seal-capable ring，仅在有界reference window以previous key验证；没有lease/registry的`AeadKeyRing`不承诺自动撤销旧ring的seal能力。
- deterministic RNG/duplicate injection 仅可通过内部 test seam/monkeypatch internal factory；不进入 `__all__`、public signature、Protocol 或 stub。第三方 `cryptography` 归 `security` extra。

### 2.3 `seed.retry_reference` 稳定 surface

`seed.retry_reference.__all__` 精确为：`RetryReferenceFoundationError`, `RetryReferencePayloadVerifier`, `RetryReferenceCodec`, `RetryReferenceSnapshot`, `create_retry_reference_codec`, `freeze_retry_reference_snapshot`。

| 符号 | 稳定 shape |
|---|---|
| `RetryReferencePayloadVerifier` | Protocol：`verify(payload: bytes) -> bool`；consumer 以闭包冻结 binding |
| `RetryReferenceCodec` | immutable/redacted；`bound_verifier(payload_verifier: RetryReferencePayloadVerifier) -> RetryReferenceVerifier` |
| `RetryReferenceSnapshot` | immutable/redacted；`issue(slot: str) -> VerifiedRetryReference` |
| `create_retry_reference_codec` | `(cipher: AeadCipher, *, namespace: str, ttl_seconds: int, skew_seconds: int) -> RetryReferenceCodec` |
| `freeze_retry_reference_snapshot` | `(codec: RetryReferenceCodec, *, entries: tuple[tuple[str, bytes, RetryReferencePayloadVerifier], ...]) -> RetryReferenceSnapshot` |
| `RetryReferenceFoundationError` | `ValueError`；`reason: Literal["invalid_input", "snapshot_fault", "unknown_slot"]`；正文只等于 reason |

- foundation 不公开 KeyProvider/key-ring/AEAD 或 time/RNG/nonce test injection，只接受 `seed.crypto.AeadCipher`。production time 来自 Seed 内部安全 runtime source；测试 time seam 不出现在 public surface/stub。
- reference v1 固定为 `rr1.<base64url(crypto-frame)>`；crypto plaintext 是 canonical `iat`、`exp`、namespace 与 opaque payload，不含业务字段。namespace 1–64 个安全字符；TTL `1..604800`；skew `0..3600` 且不大于 TTL；payload 1–2048 bytes；reference ≤4096 bytes。
- bound verifier 顺序为 framing/version/length → cipher open → iat/exp/skew → namespace → payload verifier。合法 reference 且 payload verifier exact `True` 才返回 exact `True`；malformed/tamper/unknown key/expired/wrong namespace、open rejection、payload verifier False/非 bool/异常全部返回 exact `False`，永不抛 foundation/crypto reason或泄漏内部差异。
- bound verifier 只交给既有 `verify_retry_reference` 铸造 seal；不存在“诊断并顺便 seal”或第二 verified/failure/envelope/serializer 入口。
- freeze 在外部调用前完成全部 entry shape、internal clock、framing、cipher seal、round-trip bound verification 和 `verify_retry_reference` seal；任一运行时步骤失败原子报错，不产生部分 snapshot。
- entries 为 exact tuple、数量 `1..32`；每项 exact 3-tuple；slot 为 exact str、`^[A-Za-z0-9._-]{1,64}$`、不重复；payload exact bytes且遵循上限；不接受 raw/pre-minted reference。
- snapshot 只保存 `tuple[(slot, VerifiedRetryReference)]`，不保存 cipher/key/nonce/clock/verifier/payload/raw token。issue exact-type有界查找并返回 freeze 时同一 sealed object；跨 cipher/snapshot/并发 nonce 安全由共享 `AeadKeyRing` generation 的 active-key allocator保证。

### 2.4 每个 public 入口的唯一返回/异常矩阵

| Public 入口 | 成功 | 唯一失败行为 |
|---|---|---|
| `load_aead_key_ring(...)` | immutable ring | ID/数量/material shape → `invalid_key_ring`；provider 异常/非 exact bytes → `key_provider_contract_fault` |
| `create_aead_cipher(ring)` | immutable cipher | 非当前 intact ring → `invalid_cipher` |
| `AeadCipher.seal(plaintext, aad)` | crypto frame bytes | exact type/limits → `invalid_crypto_input`；nonce exhausted/duplicate → `nonce_allocation_fault`；AEAD failure → `encryption_fault` |
| `AeadCipher.open(frame, aad)` | plaintext bytes | 任意 type/limit/malformed/unknown key/tamper/AEAD rejection统一返回 `None`，永不抛 raw/crypto exception |
| `create_retry_reference_codec(...)` | immutable codec | cipher identity、namespace、TTL/skew shape/range → `invalid_input` |
| `RetryReferenceCodec.bound_verifier(...)` | exact-bool verifier | factory 输入非法 → `invalid_input`；生成的 verifier 所有验证失败 exact `False`且永不抛 |
| `RetryReferencePayloadVerifier.verify(...)` | exact bool | consumer 异常/非 bool由 bound verifier吞并并归一 exact `False` |
| `freeze_retry_reference_snapshot(...)` | 完整 immutable snapshot | entries shape → `invalid_input`；clock/crypto/round-trip/seal runtime fault → `snapshot_fault`，无部分结果 |
| `RetryReferenceSnapshot.issue(slot)` | 同一 sealed object | unknown/bool/subclass/raw slot → `unknown_slot` |

每个 public reason 均在上表有可观察来源；`open` rejection 与 bound verification 不另设不可观察 reason。foundation 三个 reason 不引用未导出 alias。依赖固定为 `seed.retry_reference → seed.crypto` 及 `seed.retry_reference → seed.retry → seed.errors`；crypto/errors/retry 均不反向 import foundation，errors/retry 不依赖 crypto。

## 3. 兼容策略

- `0.1.0` 已以 Delivery `maia-seed.retry-contract.0.1.0.b1e5af73` 发布，wheel SHA-256 为 `b1e5af73b9571ee730212f51f76d858e1944ff755ceb1531c63cfc5b9546303c`。`0.2.0` additive 新增 `seed.crypto` 与 `seed.retry_reference`；provenance 是兼容安全修复，不改变合法 errors/retry surface。
- 本轮不弃用 symbol。未来改变合法 public symbol/reason/wire decoder 先发 `DeprecationWarning` 并保留至少一个完整 minor；破坏删除升 major并登记最早 removal major。
- consumer 旧本地 wire format不倒灌 Seed。迁移为 add → migrate → remove：新引用只由 Seed crypto/foundation seal；legacy adapter 只读、不签发，最多保留旧 `TTL+skew`，契约通过且窗口结束后删除。
- previous key retention 覆盖 reference window；rotation创建新ring/cipher与新active-key allocator。运维SHOULD使用全新key ID/material并让新composition不再持有旧seal-capable ring，迁移期仅用previous key读取；库本身不跨ring共享guard或撤销旧对象。
- 升级前保存 consumer code/declaration/lock/adapter 的完整可校验 snapshot，再锁定同一个 `0.2.0` wheel version+SHA并运行 foundation command。失败原子恢复上一 snapshot与精确 `0.1.0`/SHA，不重解 lock、不覆写或删除制品。sealed Python object 不跨进程/pickle/wheel version，升级后从 raw reference 重验。

## 4. 实现结构

```text
seed.retry_reference ──> seed.crypto
         │
         └─────────────> seed.retry ──> seed.errors
```

- `seed.crypto` facade + internal key-ring/AEAD/ring-generation nonce allocator；`seed.retry_reference` facade + internal framing/time/snapshot。internal helper 单文件 ≤300 行、函数 ≤50 行，collision test seam不导出。
- errors/retry 只做 provenance predicate 复用的最小修复；errors 不 import retry，crypto/errors/retry 均不 import foundation。
- architecture tests 机械检查 public exports/单向 imports、foundation 未定义 KeyProvider/AEAD/seal、public signature/stub 不含 random/clock/nonce seam。
- S2-C01在`tests/unit/test_crypto.py`随实现提交collision场景：非public seam令同ring cipher A先占nonce N、cipher B首次碰撞N，B必须经共享guard重取，或耗尽后固定`nonce_allocation_fault`；同时覆盖并发、多cipher、cipher-local错误对照及跨ring概率边界。该测试进入项目登记的unit/precommit suite，test seam不进入public surface或wheel contract，也不属于Mud case。
- S2-Q01的library-quality拒绝dirty、untracked或未提交的源码，在source-clean的最终提交上执行登记质量链；PASS quality JSON写入完整`source_commit`。collision可信度来自测试与实现同commit、unit suite收集、整体quality PASS及该字段绑定，不要求runtime另产固定node、独立命令结果或日志摘要。
- S2-P01的library-package读取本Sprint PASS quality JSON，要求当前完整commit与JSON `source_commit` exact相同，并拒绝影响构建的worktree变化；不匹配即回到quality。package state写入同一`source_commit`及该quality JSON文件的`quality_evidence_sha256`，Build Once candidate继承此状态，无需consumer访问provider工作区。
- 其余provider tests覆盖reflection provenance、ring active/previous/invalid material、seal/open/tamper、codec expiry/skew/namespace/limits、snapshot原子性/外部 mutation、sensitive repr/error与strict type negatives。消费者随机nonce样本只能验证基本seal，不能证明共享guard或关闭nonce门禁。

## 5. 消费者矩阵

| 消费者 | 使用入口 | session / 目标 | 强制契约命令 |
|---|---|---|---|
| `maia-mud` | opaque payload/binding adapter；Seed 不 import/读取 consumer | worktree `/Users/ws/space/git/mai/maia/maia-mud/.harness/worktrees/sprint-2-wecom-capability-api`；Sprint/task `sprint-2-wecom-capability-api` / `S2-D02`；session/digest 见第1章；目标 exact `0.2.0` wheel+SHA | `seed_retry_foundation_contract = ["uv", "run", "python", "scripts/verify_seed_retry_foundation.py"]` |

脚本的 `successful_cases` 初始为空；case 只能在对应断言全部成功，或固定 argv 外部命令返回0、确有测试收集且证据解析成功后追加。异常、缺命令、非零、skip/xfail、case不足或artifact失败均非零退出且不得输出 `ok=true`：

- 独立旧RC命令未设置`HARNESS_RETRY_CONTRACT_TARGET_VERSION`时默认且严格验证`0.1.0`；foundation编排只给旧RC子进程显式设置该变量为`0.2.0`，调用真实固定子命令并对同一candidate要求`ok=true`、package/version/SHA一致及RC-VALID/INVALID/ISSUER/FAULT exact set。变量只允许`0.1.0|0.2.0`，未知/空白/版本不一致失败；这不放宽旧capability默认版本。
- `RRF-PROVENANCE-001` 绑定 reflection forged classifier/compose双reason与合法链；`RRF-SNAPSHOT-001` 只绑定candidate wheel公开行为：四slot freeze均为合法sealed references、重复issue返回freeze时同一对象、freeze后调用方material/payload/verifier变化不影响issue、issue不再读取key/cipher/clock/verifier/raw token、unknown slot失败关闭；不声明或推断内部guard。`RRF-FOUNDATION-001` 绑定previous/tamper/expiry/namespace/binding正反例；`RRF-OWNERSHIP-001` 绑定真实application adapter和architecture命令。
- `RRF-HTTP-001` 固定执行 `tests/integration/test_wecom_fault_boundary.py` 与真实 issuer/service chain 测试；`RRF-SOAK-001` 固定执行 `tests/performance/test_wecom_provider_soak.py`，强制 duration=300、唯一run id、新artifact，并校验 elapsed≥300、target/actual concurrency=50、P99<8及cross-talk/pending/lease/ownership/task/loop/leak全0。默认0.25秒或旧artifact均失败。

任何 contract 断言前，隔离子进程须校验wheel ZIP/METADATA/version/SHA，并逐一证明 `seed`、`seed.errors`、`seed.retry`、`seed.crypto`、`seed.retry_reference` 的规范化 `__spec__.origin`/`__file__` 都位于同一精确 candidate wheel且成员存在，distribution version为`0.2.0`、alias identity成立；site-packages/source/editable/另一wheel/`None`/混合origin均失败。HTTP与soak测试进程也必须输出可解析的四模块origin witness并绑定同一SHA。consumer不读取provider root/source commit、不运行provider工作区pytest，也不以随机样本推断内部guard；外部命令只用固定argv list与本地artifact，不用shell、网络或floating source。

当前门禁：Mud脚本已登记并完成证据硬化、可启动且在缺candidate env时安全失败；S2-V01在Build Once `0.2.0` candidate上真实运行全部case。设计阶段没有candidate或不实际等待300秒，不得预报HTTP/soak成功。

旧 `seed_retry_contract = ["uv", "run", "python", "scripts/verify_seed_retry_contract.py"]` 只归 `retry-contract` / `0.1.0`，不得替代当前 session command。Seed provider commands 为 `uv run --frozen pytest -q tests/unit/test_errors.py tests/unit/test_retry.py tests/unit/test_crypto.py tests/unit/test_retry_reference.py tests/architecture/test_boundaries.py --no-cov` 与 `uv run --frozen mypy src/seed tests`。

## 6. 交付方案

1. S2-C01 同一受审变更实现 `seed.crypto`、foundation、provenance 修复及 provider tests；任一层缺失即失败。
2. S2-Q01在source-clean final commit运行登记的unit/precommit/coverage/质量链，PASS quality JSON绑定完整`source_commit`；S2-P01要求当前commit exact等于该字段且worktree不影响构建，package state写`source_commit`与quality JSON的`quality_evidence_sha256`后才运行一次`package_build = ["uv", "build"]`。
3. S2-V01只对同一wheel运行公开Seed checks和Mud foundation command；通过package state继承`source_commit`与`quality_evidence_sha256`身份，不重跑、下载或推断internal collision seam。旧RC真实复用，每个consumer case动态产生，四模块及HTTP/soak绑定同一candidate origin；reflection、snapshot mutation、本地common implementation残留、HTTP/300秒soak证据缺失或digest mismatch均失败关闭。
4. S2-L01 Delivery继承package state的`source_commit`与`quality_evidence_sha256`，并绑定当前request digest、version/wheel SHA、签名、SBOM、provenance和真实supply-chain receipt；staged/release不重建、不改名、不换digest。
5. provider artifact 永不覆写；consumer adoption失败按第3章回退；legacy adapter只在窗口结束且 foundation contract通过后删除。
