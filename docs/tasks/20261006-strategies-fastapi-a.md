---
Date: 2026-10-06
Genre: task digest
Status: current
Scope: Strategy and complexity for the fastapi_* tasks from fastapi_11194 to fastapi_14372 inclusive (25 tasks); no runs/results were reviewed.
Source of truth: data/raw/tasks.jsonl; read 2026-10-06.
Limits: regenerable snapshot of the public task corpus; no random sampling.
---

# FastAPI strategies — block A (fastapi_11194 → fastapi_14372)

Single source: `data/raw/tasks.jsonl` (129 records). Neither `runs/` nor `results/` were reviewed.
Scope: alphabetical order of `instance_id`, from `fastapi_11194` to `fastapi_14372` inclusive.
Note: in that alphabetical range there are **25 real tasks**, not ~34 (the request estimate overstates it; the full fastapi listing in the dataset is 67 ids and the 11194–14372 slice yields 25).

Complexity criterion used throughout the document:
- **Low**: 1 file, point change (<15 effective lines), statement with a clear repro.
- **Medium**: 1–3 files or branching logic (aliases, validation/serialization modes, multidicts), required API with exact names.
- **High**: 4+ files, runtime refactor (routing/middleware/dependencies), or cross-compatibility (Starlette/Pydantic/Python) where one detail breaks everything.

---

## fastapi_11194 — `File` declared after `Form` returns 422

- **What it is:** an endpoint with `File` + `Form` fails with 422 if the `File` is not declared first; parameter order should not matter.
- **What is missing:** modify `fastapi/dependencies/utils.py`, function `_extract_form_body`. The gold uses `field.field_info` of **each** field in the loop instead of `first_field.field_info` of the first field (2 conditions: `isinstance(field_info, params.File)` and `is_bytes_sequence_field`).
- **How it is solved:**
  1. Read `fastapi/dependencies/utils.py` → `_extract_form_body` and `_get_multidict_value`.
  2. Reproduce with `tests/test_file_and_form_order_issue_9116.py` (look at the test_patch: it tests reversed order + multiple files).
  3. Change `first_field_info` to `field_info` per iteration; verify that `UploadFile` is read (`await value.read()`) and byte sequences are serialized per field, not by the first one.
  4. Verify: run the new test + `test_request_form_models` / existing upload tests.
- **Complexity:** Low (1 file, ~4 lines, very clear statement).
- **Blockers:** none regarding new names; trap: do not "reorder" params or touch the router, the fix is per-field.

## fastapi_11355 — stringified annotations are not evaluated on Python 3.10

- **What it is:** with `from __future__ import annotations` (or string annotations) on 3.10, dependencies do not resolve types; same bug as typer#598.
- **What is missing:** modify `fastapi/dependencies/utils.py`: `get_typed_signature` and `get_typed_return_annotation` must pass `eval_str=True` to `inspect.signature` when `sys.version_info >= (3, 10)`; add `import sys`.
- **How it is solved:**
  1. Read `get_typed_signature`, `get_typed_annotation`, `get_typed_return_annotation` in `dependencies/utils.py`.
  2. Repro: endpoint with a string annotation on 3.10, check that `get_typed_signature` returns unevaluated strings.
  3. Add the `eval_str=True` branch only on ≥3.10 (on <3.10 the kwarg does not exist / changes semantics).
  4. Verify: `tests/test_stringified_annotations_simple.py` + dependency suite.
- **Complexity:** Low (1 file, 2 identical hunks, known typer#721 fix).
- **Blockers:** `eval_str` only exists/is safe on ≥3.10 — do not apply it unconditionally; trap: `get_typed_annotation` with `globalns` already exists, do not duplicate logic there.

## fastapi_12942 — discriminated union with `Tag`/`Discriminator` treated as query

- **What it is:** `Annotated[ApplePie, Tag] | ...` with `Discriminator(...)` is not detected as body; FastAPI sends it to query and validates it wrong. The manual workaround was `Annotated[Dessert, Body()]`.
- **What is missing:** modify `fastapi/_compat.py`, function `field_annotation_is_complex`: add branch `if origin is Annotated: return field_annotation_is_complex(get_args(annotation)[0])` (unwrap `Annotated` nested inside `Annotated`).
- **How it is solved:**
  1. Read `fastapi/_compat.py` → `field_annotation_is_complex` and how it decides body vs query.
  2. Repro with the `Pie/ApplePie/PumpkinPie` example from the statement via TestClient (POST without explicit `Body()`).
  3. Add the recursive `Annotated` branch before the final `return`.
  4. Verify: `tests/test_union_body_discriminator.py` (large test_patch, ~8KB: several discriminator cases).
- **Complexity:** Low (1 file, 3 lines, but the test is extensive — read it first so as not to break variants).
- **Blockers:** `Tag`, `Discriminator` from pydantic — do not reimplement; trap: only unwrap `args[0]`, not all args.

## fastapi_13207 — computed fields disappear with `separate_input_output_schemas=False`

- **What it is:** the output schema omits `computed_fields` when the app uses `separate_input_output_schemas=False`.
- **What is missing:** modify `fastapi/_compat/v2.py`: in `get_schema_from_model_field` and `get_definitions`, do not force `override_mode="validation"` when there are computed fields (inspect `field._type_adapter.core_schema["schema"]["computed_fields"]`).
- **How it is solved:**
  1. Read `fastapi/_compat/v2.py` → both functions and what `override_mode` does.
  2. Repro: model with `@computed_field`, app with `separate_input_output_schemas=False`, compare OpenAPI output vs `True`.
  3. Implement the guard `len(computed_fields) > 0` / `has_computed_fields` that forces `override_mode=None`.
  4. Verify: `tests/test_computed_fields.py`.
- **Complexity:** Medium (1 file, 2 coupled functions; requires exactness in the `field_mapping[(field, mode)]` mapping).
- **Blockers:** internal names `core_schema["schema"]["computed_fields"]`, `override_mode`, `field_mapping`; trap: the fix goes in **both** functions, not just one.

## fastapi_13537 — form with empty string and default `None` breaks validation

- **What it is:** regression from #12134: form `""` is interpreted as absent, the default `None` is taken, but on the second pass `""` is re-added and validation explodes. Real HTML-forms case.
- **What is missing:** modify `fastapi/dependencies/utils.py`, `process_fn` (`_extract_form_body`/`process_fn` hunk): track `field_aliases = {field.alias for field in body_fields}` and in the extras loop check `if key not in field_aliases` instead of `if key not in values`.
- **How it is solved:**
  1. Read `process_fn` entirely (both passes: known values + extras from `received_body.items()`).
  2. Repro: optional form with default `None`, POST with `""`, expect 200 with `None`.
  3. Apply the one-line change (set of visited aliases).
  4. Verify: `tests/test_form_default.py`.
- **Complexity:** Low (1 effective line, but requires understanding both passes so as not to break `extra="allow"`).
- **Blockers:** `field.alias` vs `key` — compare against aliases, not against `values` (which may not contain the key precisely because it is `None`).

## fastapi_13713 — add `external_docs` to `FastAPI` and to the OpenAPI

- **What it is:** feature: `openapi_external_docs` parameter in the `FastAPI` constructor that must appear as `externalDocs` at the OpenAPI root.
- **What is missing:** create/modify in 2 files: `fastapi/applications.py` (new kwarg `openapi_external_docs: Annotated[Optional[Dict[str, Any]], Doc(...)] = None`, store `self.openapi_external_docs`, pass it as `external_docs=` in `self.openapi()`) and `fastapi/openapi/utils.py` (new kwarg `external_docs` in `get_openapi` + `output["externalDocs"] = external_docs`).
- **How it is solved:**
  1. Read `FastAPI.__init__` (giant signature with `Annotated[..., Doc(...)]`), method `openapi()`, and `get_openapi()` in `openapi/utils.py`.
  2. Copy the `openapi_tags`/`servers` pattern: Doc-string, default `None`, `self.*`, threading through to `get_openapi`.
  3. In `get_openapi`, add `if external_docs: output["externalDocs"] = external_docs` before `jsonable_encoder(OpenAPI(**output)...)`.
  4. Verify: `tests/test_application.py` + check `app.openapi()["externalDocs"]`.
- **Complexity:** Medium (2 files, new public API with an exact name; the `Doc()` is verbose but mechanical).
- **Blockers:** exact names `openapi_external_docs` (constructor/attribute) and `externalDocs` (OpenAPI key); trap: respect `exclude_none=True` (if it is `None` the key must not appear).

## fastapi_13786 — security returns 403 instead of 401 without credentials

- **What it is:** security classes return 403 when credentials are missing; by standard it must be 401 + `WWW-Authenticate` header. Includes the escape hatch `not_authenticated_status_code` (the statement warns that the description is partially outdated — read the test, not the text).
- **What is missing:** refactor in `fastapi/security/api_key.py` (new `APIKeyBase.__init__`, method `make_not_authenticated_error()` → 401 + `WWW-Authenticate: APIKey`, instance `check_api_key(self, api_key)`; the 3 subclasses `APIKeyQuery/Header/Cookie` delegate), `fastapi/security/http.py` (`HTTPBase.make_authenticate_headers()` + `make_not_authenticated_error()`, `HTTPBasic`/`HTTPBearer`/`HTTPDigest` use them; changes detail `"Invalid authentication credentials"` → `"Not authenticated"`), `oauth2.py`, `open_id_connect_url.py` (same pattern + `not_authenticated_status_code`), plus `docs_src/` (tutorial003* ×5, new `authentication_error_status_code/`).
- **How it is solved:**
  1. Read the new tests first (`test_security_api_key_*`, bearer, oauth2) — they define the expected status/headers/detail; the problem statement lies in the details.
  2. Implement `make_not_authenticated_error` per class (APIKey→`APIKey`, Bearer→`Bearer`, Basic→`Basic realm=...`, Digest→`Digest`).
  3. Add `not_authenticated_status_code` as a temporary workaround where applicable.
  4. Update `docs_src/security/tutorial003*` (the detail changes) and add the `authentication_error_status_code` tutorial.
  5. Verify: the entire `test_security_*` suite (there are many files; run them all).
- **Complexity:** High (11 files in gold, behavior change with breaking changes, headers per scheme).
- **Blockers:** top blockers of the block: `make_not_authenticated_error`, `make_authenticate_headers`, `not_authenticated_status_code`, exact detail `"Not authenticated"`, headers `WWW-Authenticate: APIKey|Bearer|Basic|Digest`; major trap: old tests expecting 403 must migrate to 401 unless overridden.

## fastapi_13920 — PEP 695 `TypeAliasType` support

- **What it is:** `type X = ...` (3.12+ syntax) produces `TypeAliasType`; FastAPI does not unwrap it and the dependency fails. Continuation of #11140.
- **What is missing:** modify `fastapi/dependencies/utils.py`, function `analyze_param`: import `is_typealiastype` (vendored from `typing-inspection` via `typing_inspection.typing_objects`) and if `is_typealiastype(annotation)`, do `annotation = annotation.__value__` before processing.
- **How it is solved:**
  1. Read `analyze_param` (start: where `annotation` is normalized → `type_annotation`/`use_annotation`).
  2. Add the import + 3-line unwrap right after initializing `type_annotation/use_annotation`.
  3. Verify: `tests/test_dependency_pep695.py`. Note the external dependency `typing-inspection` — check that it is installed (gold imports it, does not vendor it inline except the helper).
- **Complexity:** Low (1 file, 3 lines + import; but only testable on 3.12+).
- **Blockers:** `is_typealiastype`, `__value__` (exact name of the PEP 695 attribute); `typing-inspection` dependency; trap: unwrap **before** assigning `use_annotation`.

## fastapi_14077 — Starlette ≥0.48 compatibility (`HTTP_422_UNPROCESSABLE_ENTITY` deprecated)

- **What it is:** Starlette 0.48 renames it to `HTTP_422_UNPROCESSABLE_CONTENT` and deprecated the old one (RFC 9110). FastAPI must stop importing the old name to avoid emitting warnings, without breaking compat with Starlette<0.48.
- **What is missing:** in `fastapi/exception_handlers.py` (remove the import, use the literal `422`), `fastapi/openapi/utils.py` (`http422 = "422"`, remove the import), `docs_src/handling_errors/tutorial005.py` (`status_code=422`).
- **How it is solved:**
  1. `grep HTTP_422_UNPROCESSABLE` across the whole repo — gold touches 3 files but there may be more occurrences.
  2. Replace with the literal `422`/`"422"` (not with the new name, so as not to break old Starlette).
  3. Verify: `tests/test_enforce_once_required_parameter.py` + grep that no imports of the old symbol remain + run with `-W error::DeprecationWarning` if possible.
- **Complexity:** Low (mechanical, 3 files; the criterion is to use neither the old name nor the new one).
- **Blockers:** literal `422` as int (handlers) and `"422"` as str (`responses` key in OpenAPI); trap: do not raise the Starlette pin more than needed or use `HTTP_422_UNPROCESSABLE_CONTENT`.

## fastapi_14099 — `StreamingResponse` + `yield`/`UploadFile` dependencies close too early

- **What it is:** with `StreamingResponse`, the exit code of dependencies with `yield` (and `UploadFile`s) runs before the stream finishes; it must run **after** sending the response.
- **What is missing:** create `fastapi/middleware/asyncexitstack.py` (new `AsyncExitStackMiddleware` that sets `scope["fastapi_middleware_astack"]`); rewrite in `fastapi/routing.py` `request_response` and `websocket_session` (copies of Starlette with their own `AsyncExitStack` `scope["fastapi_inner_astack"]`, flag `response_awaited` + `FastAPIError` if not awaited) and `get_request_handler` (double stack: close files after the response); touch `fastapi/applications.py` (register the middleware); plus 2 example `docs_src`.
- **How it is solved:**
  1. Read the current `routing.py:get_request_handler` and the Starlette versions (`request_response`, `websocket_session`, `wrap_app_handling_exceptions`, `is_async_callable`).
  2. Implement the new middleware first (it is the smallest and testable in isolation).
  3. Port the Starlette copies with the stack hooks; keep `JSONDecodeError`/`HTTPException` handling identical.
  4. Verify: `test_dependency_after_yield_streaming.py`, `test_dependency_after_yield_websockets.py`, `test_dependency_after_yield_raise.py`, `test_dependency_contextmanager.py`. These are timing/close tests — run them several times.
- **Complexity:** High (5 files, a fork of Starlette internals that must follow its exception semantics; the slightest deviation breaks websockets or streaming).
- **Blockers:** scope names `fastapi_middleware_astack` / `fastapi_inner_astack`, `AsyncExitStackMiddleware`, message `FastAPIError("Response not awaited...")`; dependencies: Starlette version (imports `starlette._exception_handler`, `starlette._utils` — private, fragile to upgrades); trap: the `except Exception: pass` with `yield` that swallows the response exception (the `response_awaited` exists precisely for that).

## fastapi_14186 — internal Pydantic v1 compatibility on Python 3.14 / Pydantic 2.12.1

- **What it is:** on 3.14 + Pydantic 2.12 (which dropped v1 and warns when importing `v1`), FastAPI imported `v1` unconditionally and the 3.14 tests failed. Every `v1` import must be avoided in that environment.
- **What is missing:** create `fastapi/_compat/may_v1.py` (shim: on ≥3.14 defines dummies `AnyUrl/BaseConfig/BaseModel/Color/ModelField/...` + `get_definitions` returning `({}, {})`; on <3.14 re-exports from `.v1`); and in `main.py`, `shared.py`, `v1.py`, `v2.py`, `dependencies/utils.py`, `encoders.py`, `temp_pydantic_v1_params.py`, `utils.py` replace `isinstance(x, v1.ModelField)` / `issubclass(y, v1.BaseModel)` with `may_v1.*` using a lazy import (`from fastapi._compat import v1` inside the branch that needs it), plus `import sys` and `sys.version_info < (3, 14)` branches.
- **How it is solved:**
  1. Read `may_v1.py` from gold if it exists in the checkout, otherwise design it according to the diff: dummies with the same names + `get_definitions` stub.
  2. `grep "from fastapi._compat import v1\|import v1\|v1\.ModelField\|v1\.BaseModel"` and migrate each site to the lazy-import pattern.
  3. Watch out for `get_definitions` in `main.py`: on 3.14 only v2; on <3.14 merge of both dicts.
  4. Verify: `tests/test_compat.py` + pydantic suite on the environment's Python; on <3.14 nothing should change (typical silent regression).
- **Complexity:** High (10 files, the largest in the block ~26KB; circular imports lurking — that is why the imports are lazy/inside functions).
- **Blockers:** `may_v1` (exact module name), `sys.version_info >= (3, 14)` as the condition, dummies with names identical to v1; trap: `lru_cache`/`get_cached_model_fields` interact with the dummies — do not cache fake types.

## fastapi_14246 — schema separation with nested models (0.119.0 regression)

- **What it is:** the validation/serialization separation breaks with nested models (issue #14247, discussion #14177).
- **What is missing:** modify `fastapi/_compat/v2.py`, `get_definitions`: instead of a single `flat_models`/`flat_model_fields`, compute `flat_validation_models` and `flat_serialization_models` separately (with `mode="validation"` / `mode="serialization"` on each `ModelField`) and concatenate.
- **How it is solved:**
  1. Read `get_definitions` + `get_flat_models_from_fields` in `_compat/v2.py`.
  2. Repro with the new tests (`test_no_schema_split.py`, multifile) — they are 10KB of cases, read them before coding.
  3. Split the computation by mode as in the diff; keep `input_types`/`unique_flat_model_fields` the same.
  4. Verify: both test files + `test_computed_fields.py` (neighboring area that also touches `get_definitions`).
- **Complexity:** Medium (1 file, ~20 lines, but the case space — nested × modes — is large).
- **Blockers:** `mode="validation"` / `mode="serialization"` on the synthetic `ModelField`s; trap: do not mix `known_models` between modes (separate sets).

## fastapi_14258 — clear error when including a router into itself

- **What it is:** `router.include_router(router)` hangs/recurses with no message; a clear `AssertionError` is requested.
- **What is missing:** modify `fastapi/routing.py`, `APIRouter.include_router`: `assert self is not router, ("Cannot include the same APIRouter instance into itself. Did you mean to include a different router?")` before the `prefix` asserts.
- **How it is solved:**
  1. Read `include_router` in `routing.py` (docstring with example).
  2. Add the assert in first position.
  3. Verify: `tests/test_router_circular_import.py` (check the message match if it uses `pytest.raises(..., match=...)`).
- **Complexity:** Low (1 file, 4 lines; the only thing that matters is the exact message).
- **Blockers:** exact message `"Cannot include the same APIRouter instance into itself. Did you mean to include a different router?"`; trap: `is not` (identity), not `!=`.

## fastapi_14262 — dependencies with `scope` (`"request"` vs `"function"`)

- **What it is:** large feature: `Depends(func, scope="request"|"function")`; `"function"` runs the `yield` exit after the function but **before** sending the response. Includes an error if a `"request"` dependency depends on a `"function"` one.
- **What is missing:** `fastapi/params.py` (`Depends.scope` + plumb in `Security`), `fastapi/dependencies/models.py` (`Dependant.scope`, `computed_scope`, `cache_key` now includes scope via `DependencyCacheKey`, `cached_property is_gen/is_async_gen/is_coroutine_callable` moved from utils), `fastapi/dependencies/utils.py` (`get_dependant(..., scope)`, propagation in sub-dependants, `DependencyScopeError` when request→function, `_solve_generator(dependant=...)` choosing `request_astack` vs `function_astack`), `fastapi/routing.py` (create both stacks in scope), `fastapi/exceptions.py` (`DependencyScopeError`), `fastapi/types.py` (`DependencyCacheKey`), plus `docs_src/dependencies/tutorial008e*`.
- **How it is solved:**
  1. Read the current `models.py` (Dependant), `get_dependant`, `solve_dependencies`, `solve_generator` end to end before touching anything.
  2. Implement in order: `types.py` → `exceptions.py` → `models.py` → `params.py` → `utils.py` → `routing.py`.
  3. Validation rule: gen-request depending on gen-function → `DependencyScopeError('The dependency "..." has a scope of "request", it cannot depend on dependencies with scope "function".')`.
  4. Verify: `test_dependency_yield_scope.py` + websockets + tutorial008e. Cleanup-order tests — fragile, run repeatedly.
- **Complexity:** High (10 files, ~19KB; concurrent lifecycle semantics + cache key that changes → invalidates old caches).
- **Blockers:** exact values `"function"`/`"request"`, `DependencyScopeError`, `DependencyCacheKey` (3-tuple with scope), scopes `fastapi_inner_astack`/`fastapi_function_astack`; trap: `cache_key` goes from 2-tuple to 3-tuple — any monkeypatch/tests that build it by hand break.

## fastapi_14266 — top-level app security schemes do not appear in the OpenAPI

- **What it is:** `SecurityBase` passed directly to the app (not as an endpoint parameter) does not generate `securityRequirements` in the OpenAPI.
- **What is missing:** modify `fastapi/dependencies/utils.py`, `get_dependant`: move the `SecurityRequirement` registration to the beginning — if `call` itself `isinstance(call, SecurityBase)`, append `SecurityRequirement(security_scheme=call, scopes=...)` to the `dependant` (instead of only when it appears as a sub-dependant's `param_details.depends.dependency`).
- **How it is solved:**
  1. Read `get_dependant` (where `security_requirements` are created today: only in the sub-dependants branch).
  2. Move/create the `isinstance(call, SecurityBase)` block before the `signature_params` loop (with `use_scopes = security_scopes` only for `OAuth2/OpenIdConnect`).
  3. Verify: `tests/test_top_level_security_scheme_in_openapi.py`.
- **Complexity:** Low-Medium → **Low** (1 file, moving a ~10-line block; the risk is duplicating requirements if both are left).
- **Blockers:** `SecurityRequirement(security_scheme=call, scopes=use_scopes)`; trap: delete the old block from the loop or duplicates remain.

## fastapi_14297 — `Optional[List[bytes]] = File(None)` crashes with `issubclass() arg 1 must be a class`

- **What it is:** optional sequence of files: `origin_type` is `Union`, `issubclass(Union, ...)` blows up in `serialize_sequence_value` (Pydantic V2).
- **What is missing:** modify `fastapi/_compat/v2.py`, `serialize_sequence_value`: if `origin_type is Union`, iterate `get_args(...)` skipping `NoneType` and take `get_origin(arg) or arg` as the real `origin_type`.
- **How it is solved:**
  1. Read `serialize_sequence_value` and `shared.sequence_types` / `sequence_annotation_to_type`.
  2. Repro with the statement snippet (`Optional[List[bytes]] = File(None)`, POST 2 files).
  3. Add the `Union` unwrap (6 lines).
  4. Verify: `tests/test_optional_file_list.py` + `test_compat.py`.
- **Complexity:** Low (1 file, 7 lines, repro included in the statement).
- **Blockers:** `sequence_annotation_to_type[origin_type]` — the final `origin_type` must be a valid key (list/bytes); trap: skip only `type(None)`, not other args.

## fastapi_14301 — `Depends(func, scope='function')` ignored in route parameterless dependencies

- **What it is:** `scope="function"` does not work when the dependency is registered at the `APIRoute(dependencies=[...])` level because `get_parameterless_sub_dependant` did not propagate `depends.scope`.
- **What is missing:** modify `fastapi/dependencies/utils.py`, `get_parameterless_sub_dependant`: pass `scope=depends.scope` to `get_dependant` (3 lines).
- **How it is solved:**
  1. Read `get_parameterless_sub_dependant` (note it does propagate `security_scopes` but not `scope`).
  2. Add `scope=depends.scope` to the call.
  3. Verify: `tests/test_dependency_yield_scope.py` (route-level cases). Conceptually depends on 14262 — if the checkout predates that merge, first understand `scope` there.
- **Complexity:** Low (1 file, 1 kwarg; surgical fix post-14262).
- **Blockers:** `scope=depends.scope` (exact name); trap: none — but without 14262 in the tree the kwarg does not exist and must be ported.

## fastapi_14303 — `Form` with `extra="allow"` model loses lists (only the last value remains)

- **What it is:** with a `Form` model + `extra="allow"`, a multivalue extra arrives as a scalar (only the last). Cause: `received_body.items()` collapses repeated keys.
- **What is missing:** modify `fastapi/dependencies/utils.py`, `process_fn` (extras tail): iterate `received_body.keys()` and use `received_body.getlist(key)` (1 value → scalar, N → list).
- **How it is solved:**
  1. Read the tail of `process_fn` (`field_aliases` block — comes from 13537, the diff assumes that state).
  2. Repro with the statement snippet (`param2=["456","789"]`).
  3. Change `for key, value in received_body.items()` to `for key in received_body.keys()` + `getlist`.
  4. Verify: `tests/test_forms_single_model.py`.
- **Complexity:** Low (1 file, ~5 lines; twin of 14356).
- **Blockers:** `getlist` (`FormData`/multidict API); trap: keep it a scalar when `len==1` or it breaks all existing simple extras.

## fastapi_14306 — tracebacks with endpoint metadata (file/line/function/method/route)

- **What it is:** DX feature: `RequestValidationError`/`ResponseValidationError` include endpoint context (clickable file in IDEs, line, function, method+route) only in `str(exc)` (logs), never in the 422 sent to the client. Cached (benchmark: 0.06µs/req).
- **What is missing:** `fastapi/exceptions.py` (new `EndpointContext(TypedDict)` + `ValidationException.__init__(..., endpoint_ctx)` + `_format_endpoint_context()` + `__str__`; same kwargs on `Request/WebSocket/ResponseValidationError`; the old `__str__` of `ResponseValidationError` is removed), `fastapi/routing.py` (`_extract_endpoint_context(func)` with `_endpoint_context_cache: Dict[int, EndpointContext]`, `serialize_response(..., endpoint_ctx)`, construction of `endpoint_ctx` in `get_request_handler.app` with `mount_path`/`root_path`, threading to the `raise`s).
- **How it is solved:**
  1. Read `exceptions.py` (`ValidationException` hierarchy) and `routing.py` (`get_request_handler`, `serialize_response`).
  2. Implement `exceptions.py` first (types + format; pure unit test without a server).
  3. Then `routing.py`: extractor with cache by `id(func)` + `try/except` (never break the request due to introspection), pass `endpoint_ctx` at the 3 raise sites.
  4. Verify: `tests/test_validation_error_context.py`; assert that the HTTP 422 body does **not** contain local paths (leak check).
- **Complexity:** Medium (2 files, ~8.5KB; exact string format + no-leak-to-client invariant).
- **Blockers:** `EndpointContext` (`function/path/file/line`), format `'  File "{file}", line {line}, in {func}'` + `'    {METHOD} {path}'`, `_endpoint_context_cache`; double trap: 1) the old `str()` said `"N validation errors:"` (fixed plural) vs the new singular/plural; 2) cache by `id()` can collide after GC — accepted in gold, do not "improve" it.

## fastapi_14349 — schema attribute named `$ref` breaks `_replace_refs`

- **What it is:** a model with a field literally named `$ref` makes `_replace_refs` treat its value (a dict/schema, not a string) as a reference and blow up or corrupt.
- **What is missing:** modify `fastapi/_compat/v2.py`, `_replace_refs`: `value = schema["$ref"]; if isinstance(value, str):` before `split("/")` / remapping; if it is not a str, it is left untouched (and recursion into dicts continues).
- **How it is solved:**
  1. Read `_replace_refs` (recursion over dicts).
  2. Repro: model with a `$ref` field (see `tests/test_schema_ref_pydantic_v2.py` + issue #14344).
  3. Add the `isinstance(value, str)` guard.
  4. Verify: new test + schema suite.
- **Complexity:** Low (1 file, ~5 lines, type guard).
- **Blockers:** none regarding names; trap: do not confuse with 14361 (same neighborhood, different fix).

## fastapi_14356 — `Query`/`Header` with `extra="allow"` model loses lists (twin of 14303)

- **What it is:** same bug as 14303 but in `request_params_to_args` (query/header/no-body params). Cookies excluded (spec: no multivalue; only comma-separated, not supported by Starlette).
- **What is missing:** modify `fastapi/dependencies/utils.py`, `request_params_to_args` (extras tail): iterate `received_params.keys()`, use `getlist` if present (`hasattr` guard because query/header may not be multidict on all paths), `len==1` → scalar.
- **How it is solved:**
  1. Read `request_params_to_args` (extras tail; note the difference from `process_fn`: here there is `hasattr(received_params, "getlist")` fallback to `.get`).
  2. Repro with the snippet (`Query` model, `param2=[456,789]`).
  3. Apply the change.
  4. Verify: `tests/test_query_cookie_header_model_extra_params.py` + header models tutorial.
- **Complexity:** Low (1 file; the `hasattr` is the only detail vs 14303).
- **Blockers:** `getlist` with an `hasattr` guard (do not assume multidict always); trap: cookies — do not try to fix them here.

## fastapi_14360 — alias in `Query`/`Header`/`Cookie` models validates wrongly

- **What it is:** with a params model and `alias`, the value is extracted by alias but stored with `field.name` → the validator (which looks up by alias) fails; moreover `field.name` is put into `processed_keys` and hides extras passed by name.
- **What is missing:** modify `fastapi/dependencies/utils.py`, `request_params_to_args`: `params_to_process[field.alias] = value` (was `[field.name]`) and `processed_keys.add(alias or field.alias)` without adding `field.name`.
- **How it is solved:**
  1. Read `request_params_to_args` (the 3 lines: store + 2× `processed_keys.add`).
  2. Repro: Query model with `Field(alias=...)`, request by alias and by name.
  3. Change the store to `field.alias`, remove `processed_keys.add(field.name)`.
  4. Verify: `tests/test_request_param_model_by_alias.py`. Direct predecessor of 14371 (which generalizes to `validation_alias`).
- **Complexity:** Low (2 lines; requires understanding alias-vs-name in `values`/`processed_keys`).
- **Blockers:** `field.alias` as the `params_to_process` key; trap: if the checkout already includes 14371, this fix is subsumed — do not duplicate.

## fastapi_14361 — `_remap_definitions_and_field_mappings` touches schemas without `$ref`

- **What it is:** the function assumes every schema in `field_mapping` has `$ref` and does an unconditional `split` (cf. discussion #14265); with Pydantic v2 there are entries without `$ref` and it blows up.
- **What is missing:** modify `fastapi/_compat/v2.py`, `_remap_definitions_and_field_mappings`: `if model not in model_name_map or "$ref" not in schema: continue`.
- **How it is solved:**
  1. Read the function (loop over `field_mapping.items()`).
  2. Add the second condition to the `continue`.
  3. Verify: `tests/test_schema_compat_pydantic_v2.py`.
- **Complexity:** Low (1 line; the smallest fix in the block).
- **Blockers:** none; trap: do not confuse with 14349 (`_replace_refs`, a different `$ref` guard).

---

## Aggregate table

### Complexity distribution (23 tasks)

| Complexity | Count | IDs |
|---|---|---|
| Low | 15 | 11194, 11355, 12942, 13537, 13920, 14077, 14258, 14266, 14297, 14301, 14303, 14349, 14356, 14360, 14361 |
| Medium | 4 | 13207, 13713, 14246, 14306 |
| High | 4 | 13786, 14099, 14186, 14262 |

Block pattern: ~2/3 are surgical fixes in `dependencies/utils.py` or `_compat/v2.py` (Low); the real difficulty concentrates in 4 runtime/compatibility tasks that touch 4–11 files each.

### Top 5 blockers of the block (with counts)

| # | Blocker | Affected tasks (count) | Detail |
|---|---|---|---|
| 1 | `received_body`/`received_params` + `getlist` vs `.items()` (multidict extras) | 4 (13537, 14303, 14356, 14360) | The Form/Query-extra cluster: `field_aliases` + `getlist` + `len==1→scalar` + store by `alias`. If the checkout does not include 13537, 14303/14356 do not apply cleanly. |
| 2 | Exact 401 security names (`make_not_authenticated_error`, `make_authenticate_headers`, `not_authenticated_status_code`, detail `"Not authenticated"`, `WWW-Authenticate`) | 2 tasks but 11 files (13786 + carry-over in 14266) | The most expensive blocker: headers per scheme and exact detail; the 13786 statement is outdated — the test rules. |
| 3 | `scope="function"`/`"request"` + `DependencyCacheKey` + `DependencyScopeError` + stacks `fastapi_inner_astack`/`fastapi_function_astack` | 3 (14262, 14301, 14099) | Shared lifecycle infrastructure: 14099 creates the stacks, 14262 gives them semantics, 14301 fills the parameterless gap. Suggested reading order: 14099 → 14262 → 14301. |
| 4 | `validation_alias`/`serialization_alias` + `get_validation_alias` (str only) | 1 (14360; 14371 twin in block B) | 14360 is the `alias` case; 14371 (block B) generalizes it. `AliasPath`/`AliasChoices` explicitly out. |
| 5 | `$ref` guards in Pydantic v2 schemas (`isinstance(value, str)`, `"$ref" not in schema`) + `override_mode`/`mode` validation-vs-serialization | 4 (14349, 14361, 13207, 14246) | Cluster `_compat/v2.py:get_definitions` — all 4 touch the same file and neighboring functions; apply in order and run `test_computed_fields` + `test_no_schema_split` + `test_schema_*` together. |

External dependencies to watch in the block: `typing-inspection` (13920), Starlette version — private imports `starlette._exception_handler`/`starlette._utils` (14099) and the 422 rename (14077) —, Pydantic ≥2.12 + Python 3.14 without v1 (14186), `python-multipart` (all Form ones).
