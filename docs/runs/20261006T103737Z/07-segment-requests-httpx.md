---
Date: 2026-10-06
Genre: run analysis
Status: current
Scope: The requests_*/httpx_*/other segments across runs 20261004, 20261005 and 20261006T103737Z (70 executions; httpx and other have zero executions).
Source of truth: runs/20261004T225306Z/, runs/20261005T050122Z/ and runs/20261006T103737Z/; read 2026-10-06.
Limits: requests failures are environmental (httpbin fixture + offline network); no intrinsic-difficulty inference.
---

# 2026-10-06 — requests_*/httpx_*/other segments (70 executions, 3 runs)

| Prefix | Executions | Unique | Resolved | Rate |
|---|---|---|---|---|
| fastapi_* | 10 | 7 | 1 | 10% |
| requests_* | 4 | 2 (7502, 7505) | 0 | 0% |
| rich_* | 56 | 48 | 32* | ~57% |
| httpx_* | 0 | — | — | — |
| other | 0 | — | — | — |
* rich per run: run_01 2/4, run_02 1/4, run_03 29/48. Only prefixes present: fastapi/requests/rich. grep httpx only matches a client inside fastapi traces. run_03 100% rich.

requests_7502 "Fix _encode_files detection for __getattr__-based wrappers": 20261004 fail exit 1 138/4/196 patch models.py 3x isinstance→hasattr + 3 junk (3303B) 60/79/1025s; 20261005 fail 138/4/196 patch 1 site _encode_files + repro_protocol.py (1352B) 65/81/629s.
requests_7505 "Add hasattr checks for remaining protocol isinstance": 20261004 fail 138/4/197 helpers is_supports_read/items TypeGuard in _types.py + models 3 + utils 2 + 2 scripts (5902B) 34/41/384s; 20261005 fail 138/4/197 identical without scripts TypeIs (3629B) 42/47/372s.

Kinds (the 4 bit-for-bit identical: 308757B in 7502, 309609B in 7505):
A. 196/197 ERRORs fixture: tests/conftest.py:34 @pytest.fixture def httpbin(httpbin) → recursive dependency involving fixture 'httpbin'. Shadows the pytest-httpbin plugin. ~2/3 of the suite errors in setup, independent of the patch.
B. 4 FAILED TestTimeout: test_connect_timeout[x2], test_total_timeout_connect[x2]. sock.connect → OSError Errno 101 Network unreachable vs TARPIT 10.255.255.1 → urllib3 NewConnectionError → requests.adapters.py:729 raise ConnectionError. Expected ConnectTimeout, but the mapping requires not isinstance NewConnectionError. Offline ⇒ impossible.

Attribution: 138 passed / 1 skipped / 1 xfailed identical x4; zero encoding/multipart failures. resolved=false measures the harness, not the fix (correct patches, even TypeGuard/TypeIs).

Intra:
1. Total determinism: same exit, same 4 FAILED, errors 196 vs 197 stable per task.
2. Convergence same fix two ways: 7502 3xhasattr→1 site; 7505 same design both runs (they differ TypeGuard vs TypeIs, loose scripts: bad hygiene 3/4).
3. Asymmetric cost: 7502 ~2x calls/time vs 7505 (`__getattr__` experimentation).
4. Ghost signal session.log: "finished/verified" with its own repro, harness failed orthogonal.

Contrast: httpx 0 tasks (no possible contrast), other 0. requests 0/4 vs rich ~57% vs fastapi 1/10 — misleading: 0% requests is fixture+network, not intrinsic difficulty.
