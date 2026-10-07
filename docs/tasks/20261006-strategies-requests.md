---
Date: 2026-10-06
Genre: task digest
Status: current
Scope: Strategy and complexity for the 13 requests_* tasks; no runs/results were reviewed.
Source of truth: data/raw/tasks.jsonl; read 2026-10-06.
Limits: regenerable snapshot of the public task corpus; no random sampling.
---

# Strategies — 13 `requests_*` tasks (psf/requests)

Single source: `data/raw/tasks.jsonl`. Date: 2026-10-06.
Complexity criterion used throughout the document: **Low** = localised change in 1–2 files, < ~15 lines of gold patch, no network or cross-version compatibility; **Medium** = 2–4 files touched or logic with edge cases (domains/ports, redirects, MRO/pickle, typing) or a test that requires httpbin; **High** = cross-version compatibility or a dependency matrix (urllib3 1.x/2.x) or refactors that reorder tests.

## requests_7505 — Centralise `has_read()` with `SupportsRead` + `hasattr`
- **What it is:** successor to #7502. It creates `has_read()` in `src/requests/_types.py` (`isinstance(obj, SupportsRead) or hasattr(obj, "read")`, typed `TypeIs`) and replaces the 3 scattered checks in `models.py` (`_encode_params`, `_encode_files`, `prepare_body`).
- **What is missing:** the `__getattr__` proxies that only expose `read` without `__iter__` do not pass the `isinstance` check against a runtime_checkable `Protocol`; the test `test_post_getattr_proxy_read_only` (POST with a `ReadProxy` without a direct `__iter__`) fails.
- **Strategy:** 1) add `has_read()` in `_types.py` with `TypeIs[SupportsRead[str | bytes]]`; 2) import it as `_t` in `models.py` and replace the 3 `isinstance(..., _SupportsRead)` calls (including the partial `or hasattr` from #7502); 3) run the new test + `test_post_named_tempfile` as a regression.
- **Complexity:** Medium (criterion: touches 2 files at 3 sites + `Protocol`/`TypeIs` typing).
- **Blockers:** depends on #7502 (application order); a runtime_checkable `Protocol` does not see `__getattr__` proxies.

## requests_7502 — Detecting `read` in `_encode_files` for `__getattr__` wrappers
- **What it is:** in `models.py::_encode_files`, `isinstance(fp, _SupportsRead)` does not detect file wrappers that proxy via `__getattr__`; predecessor of #7505.
- **What is missing:** the `elif` must accept `or hasattr(fp, "read")`; the test `test_post_named_tempfile` (NamedTemporaryFile in `files={}`) exposes the regression.
- **Strategy:** 1) add the `or hasattr(fp, "read")` with the defensive comment; 2) verify with a real tempfile + multipart; 3) touch nothing else (the refactor to `has_read()` is #7505).
- **Complexity:** Low (<5 lines, 1 site, no network required for the fix).
- **Blockers:** `isinstance` against `Protocol` does not cover proxies; chaining with #7505.

## requests_7433 — Detecting streams in `prepare_body` for `__getattr__` proxies
- **What it is:** `isinstance(data, Iterable)` (post-2.33.1 modernisation) does not detect file-like objects that proxy `__iter__` via `__getattr__`; it breaks streams and rewind on redirects. Fix: `isinstance(data, Iterable) or hasattr(data, "__iter__")` with the exclusion of `(str, bytes, list, tuple, Mapping)`.
- **What is missing:** the file-like body falls into the wrong branch, `super_len`/rewind is not applied; test `test_getattr_proxy_stream_follows_redirect` (POST to `redirect-to?url=/post&status_code=307` with `AttrProxy`).
- **Strategy:** 1) edit the `if` in `prepare_body` (~line 596); 2) reproduce with `io.BytesIO` + `AttrProxy` and a 307 redirect; 3) check that `str/bytes/list/tuple/Mapping` remain excluded.
- **Complexity:** Low (1 condition, 1 file).
- **Blockers:** the test requires a live httpbin (real 307 redirect); the `hasattr` fix family (7502/7505/7433) is best applied together.

## requests_7427 — `no_proxy` must respect domain boundaries (port of bpo-39057)
- **What it is:** `should_bypass_proxies` did a raw `hostname.endswith(host)`: `prelocalhost` matched `localhost`, `newdomain.com` matched `newdomain.com:1234`. The fix normalises (`lstrip(".")`, exact match of host and of `host:port`, and only then a suffix match with a prepended `.`).
- **What is missing:** false bypass positives (traffic that should go through the proxy goes direct and vice versa); test `test_should_bypass_proxies_no_proxy_domain_boundary` with 9 cases (ports, subdomains, `.d.o.t`).
- **Strategy:** 1) edit the loop in `utils.py::get_proxy`; 2) build a local table of cases (exact host / host:port / subdomain / `prelocalhost` negative / different port negative); 3) run the parametrised `tests/test_utils.py`.
- **Complexity:** Medium (logic with domain+port edge cases, although the patch is short).
- **Blockers:** undefined inherited semantics (#4795) + CPython/curl parity; easy regression if the `lstrip` is reordered.

## requests_7315 — Preserve leading slashes in `request_url` (S3 presigned URLs)
- **What it is:** `adapters.py::request_url` collapsed `//key` to `/key`, breaking S3 signatures (`https://bucket.s3...//key`). Fix: delete the 2 lines of the `if url.startswith("//")`.
- **What is missing:** URLs with a double leading slash reach urllib3 mutilated; the test changes from `test_request_url_trims...` to `test_request_url_handles...` expecting `//v:h`.
- **Strategy:** 1) remove the collapse; 2) verify with `Request("GET", "http://127.0.0.1:10000//v:h").prepare()` + `HTTPAdapter().request_url(p, {})`; 3) no network needed.
- **Complexity:** Low (deletion of 2 lines, pure unit test).
- **Blockers:** direct conflict with requests_6644 (which *adds* those same lines; application order determines which wins); risk of urllib3 reinterpreting `//` as a host.

## requests_7328 — `Response.history` must not self-reference on redirects
- **What it is:** in `sessions.py::resolve_redirects`, `resp.history = hist[1:]` after `hist.append(resp)` left each response included in its own `history` (reference explosion, delayed GC). Fix: `resp.history = hist[:]` before the append.
- **What is missing:** `resp in resp.history` is True and `history[i].history != history[:i]`; test `test_redirect_history_no_self_reference` (GET to `redirect/3`, 3 entries, per-index invariant).
- **Strategy:** 1) reorder the 2 lines; 2) test with a chain of 3 redirects; 3) do not remove the intermediate assignment (it would be breaking, postponed).
- **Complexity:** Low (2 lines, 1 file).
- **Blockers:** the test requires httpbin with real redirects; the major change (removing the intermediate `.history`) is explicitly out of scope.

## requests_7309 — Ignore malformed Content-Type parameters without `=`
- **What it is:** `_parse_content_type_header` assigned `True` to params without `=` (`text/html; charset` → `{"charset": True}`), against RFC 1521–9110. Fix: only assign if `find("=") != -1` (with walrus), renames `items_to_strip` to `strip_chars`.
- **What is missing:** `get_encoding_from_headers` can derive an encoding from an invalid param; tests remove `"no_equals": True` from 4 cases and add `text/html; charset → ISO-8859-1`.
- **Strategy:** 1) rewrite the parser loop; 2) run `test_parse_dict_header` + `test_get_encoding_from_headers` in `test_utils.py`; 3) pure function, no network.
- **Complexity:** Low (1 function, unit tests).
- **Blockers:** none relevant; walrus requires py3.8+ (not a problem in this repo).

## requests_7205 — Ignore empty netrc entries (Python 3.11+ change)
- **What it is:** since 3.11, `netrc(...).authenticators(host)` returns `('', '', '')` instead of raising `NetrcParseError`, and requests sent `:` in the `Authorization` header. Fix: `if _netrc and any(_netrc)` in `get_netrc_auth`.
- **What is missing:** an empty credential treated as valid; test `test_empty_default_credentials_ignored` (netrc with `default` without user/pass → `None`).
- **Strategy:** 1) add the `any()`; 2) reproduce with a tmp netrc + `NETRC` env; 3) confirm that an explicit `auth=('', '')` still works through another path.
- **Complexity:** Low (1 condition, test with tmp_path/monkeypatch).
- **Blockers:** behaviour depends on the Python version of the interpreter (<3.11 vs 3.11+).

## requests_6757 — `super_len` compatibility with urllib3 1.x vs 2.x
- **What it is:** urllib3 2.x encodes `str` as utf-8 while 1.x/http.client uses latin-1; `super_len` must count bytes (`o.encode("utf-8")`) only on 2.x. It adds `is_urllib3_1` in `compat.py` (parsing `urllib3.__version__`) and consumes it in `utils.py`; it moves the `Content-Length` tests to module level with `skipif(is_urllib3_1)`.
- **What is missing:** `Content-Length` miscalculated for multibyte strings (☃️) depending on the version; tests moved/conditional.
- **Strategy:** 1) add version detection in `compat.py`; 2) condition the `encode` in `super_len`; 3) run the matrix with both urllib3 versions installed.
- **Complexity:** High (1.x/2.x dependency matrix + test reordering).
- **Blockers:** the environment's urllib3 version; chaining with requests_6589 (which adds the unconditional `encode` — 6757 conditions it afterwards).

## requests_6629 — `JSONDecodeError` must be picklable (process pools)
- **What it is:** `requests.exceptions.JSONDecodeError` inherits from `CompatJSONDecodeError` + `InvalidJSONError`; by MRO, `__reduce__` resolved to the one from `IOError` and `pickle.dumps/loads` lost args (`Extra data`, doc, pos). Fix: an explicit `__reduce__` delegating to `CompatJSONDecodeError.__reduce__(self)`.
- **What is missing:** any failed `r.json()` in a process pool crashes when serialising the error; test `test_json_decode_errors_are_serializable_deserializable` (round-trip + identical `repr`).
- **Strategy:** 1) add `__reduce__` in `exceptions.py`; 2) verify the round-trip with `pickle` and with json vs simplejson as `Compat`; 3) test without network.
- **Complexity:** Medium (MRO + dual json/simplejson backend, although the patch is ~10 lines).
- **Blockers:** the effective json backend (stdlib vs simplejson) changes `CompatJSONDecodeError`.

## requests_6644 — Trim excess leading slashes (predecessor of #7315)
- **What it is:** a URL with a leading `//` made urllib3 reparse the request-uri as an absolute URI with host/port. Fix: `if url.startswith("//"): url = f"/{url.lstrip('/')}"` in `adapters.py::request_url`. Closes #6643.
- **What is missing:** a malformed request-uri towards urllib3; test `test_request_url_trims_leading_path_separators` (`//v:h` → `/v:h`).
- **Strategy:** 1) add the normalisation; 2) verify with `Request(...//v:h).prepare()`; 3) pure unit test.
- **Complexity:** Low (3 lines).
- **Blockers:** direct contradiction with requests_7315 (adds vs removes it — resolved in order 6644→7315); risk of breaking S3 signatures if left applied.

## requests_6589 — `super_len` must count encoded bytes for `str`
- **What it is:** `super_len` used `len(str)` (characters) instead of utf-8 bytes, with a short `Content-Length` on multibyte. Fix: `if isinstance(o, str): o = o.encode("utf-8")` at the start. Possible fix for #6586.
- **What is missing:** `Content-Length` undercounted for non-ascii `data=str`; tests `test_content_length_for_bytes_data` and `test_content_length_for_string_data_counts_bytes`.
- **Strategy:** 1) add the `encode`; 2) verify with a string containing ☃️ (bytes vs chars); 3) note that 6757 conditions it to urllib3 2.x afterwards.
- **Complexity:** Low (3 lines + prepare tests without network).
- **Blockers:** chaining with 6757 (unconditional → conditional depending on urllib3); latin-1 vs utf-8 difference.

## requests_6592 — `too_early` alias for status code 425
- **What it is:** `status_codes.py` mapped 425 only to `unordered_collection/unordered` (WebDAV); the `too_early` alias is missing (RFC 4918/8470). Fix: add `"too_early"` to the 425 tuple.
- **What is missing:** `requests.codes.get("TOO_EARLY")` returns `None`; test `test_status_code_425` (6 lookup variants → 425).
- **Strategy:** 1) add the string to the tuple; 2) verify case-insensitive lookups; 3) trivial, no network.
- **Complexity:** Low (1 line).
- **Blockers:** none.

## Aggregate
- **Complexity distribution:** High: 1 (6757) · Medium: 3 (7505, 7427, 6629) · Low: 9 (7502, 7433, 7315, 7328, 7309, 7205, 6644, 6589, 6592). Total 13.
- **Top 5 blockers:**
  1. Live httpbin for network tests (7433 redirect 307, 7505/7502 POST multipart, 7328 redirect chain).
  2. Chained/contradictory patches with a critical application order (7502→7505; 6589→6757; 6644 vs 7315 cancel out).
  3. `isinstance` vs a runtime_checkable `Protocol` does not see `__getattr__` proxies (family 7502/7505/7433).
  4. urllib3 1.x/2.x matrix + Python version (6757 latin-1/utf-8; 7205 netrc on 3.11+).
  5. Collateral regression risks: S3 signatures with `//` (7315/6644), redirect history and GC (7328), json/simplejson backend in pickle (6629).
