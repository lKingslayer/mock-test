from time import time

from app.domain.paths import normalize_resource_path
from app.domain.status import compute_status
from app.domain.tokens import (
    decode_resource_token,
    encode_resource_token,
    get_seed_from_env,
)

seed = get_seed_from_env()  # 0 if unset
kb_id = "kb_123"
rp = normalize_resource_path("./fixtures/Doc/Report.DOCX")
now_ms = int(time() * 1000)

# Encode/decode round-trip
tok = encode_resource_token(kb_id=kb_id, resource_path=rp, created_at_ms=now_ms, seed=seed)
payload = decode_resource_token(tok)

# Status evolution
compute_status(created_at_ms=now_ms, now_ms=now_ms, salt=payload.salt, failure_rate=0.3)  # pending
compute_status(
    created_at_ms=now_ms,
    now_ms=now_ms + 350,
    salt=payload.salt,
    failure_rate=0.3,
)  # parsed
compute_status(
    created_at_ms=now_ms,
    now_ms=now_ms + 1200,
    salt=payload.salt,
    failure_rate=0.3,
)  # indexed|error