import json
import logging

from seed.secrets import SecretProvider, SecretReference


async def test_canary_absent_from_logs_errors_and_json(monkeypatch, caplog) -> None:
    canary = "seed-secret-canary-9f27"
    monkeypatch.setenv("SEED_CANARY", canary)
    provider = SecretProvider(allowed_env=frozenset({"SEED_CANARY"}), file_roots=())
    lease = await provider.open(SecretReference.parse("env://SEED_CANARY", "canary-ref"), "canary-test")
    buffer = lease.borrow()
    with caplog.at_level(logging.INFO):
        logging.getLogger("test").info("lease=%r buffer=%r", lease, buffer)
    snapshot = json.dumps({"lease": repr(lease), "buffer": repr(buffer)})
    assert canary not in caplog.text + snapshot
    lease.close()
