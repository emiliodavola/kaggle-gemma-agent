---
Date: 2026-10-06
Genre: task digest
Status: current
Scope: Strategy and complexity for the fastapi_* tasks from fastapi_14371 to fastapi_9753 inclusive (44 tasks); no runs/results were reviewed.
Source of truth: data/raw/tasks.jsonl; read 2026-10-06.
Limits: regenerable snapshot of the public task corpus; no random sampling.
---

# FastAPI strategies — block B (fastapi_14371 → fastapi_9753)

Single source: `data/raw/tasks.jsonl` (fields `problem_statement`, `patch` = gold, `test_patch`). Neither `runs/` nor `results/` was reviewed.
Block: 44 tasks in alphabetical order, from `fastapi_14371` to `fastapi_9753` inclusive.

## Complexity criterion (explicit, applied uniformly)

- **High**: gold ≥ 150 lines or ≥ 3 files, or touches a stateful subsystem (dependency cache, routing/lifespan, OpenAPI with massive snapshots, `frontend/`, SSE). Fails easily in cascade.
- **Medium**: gold of 15–150 lines in 1–2 files, branched but localized logic (scopes, headers, JSON Schema, warnings, responses).
- **Low**: gold ≤ 15 lines or a docs/scripts/tutorials change with specific, self-contained tests.

If you are unsure between two, move up one level when the `test_patch` has ≥ 5 files or massive `test_openapi_schema` snapshots.

---

### fastapi_14371 — Fix parameter aliases (`validation_alias`)
- **What it is**: closes the failing tests of #14358. Params stop using `field.alias` and move to `validation_alias` (only string supported; `AliasPath`/`AliasChoices` are deliberately left out).
- **What is missing (gold)**: `fastapi/_compat/v2.py` (props `ModelField.validation_alias`, `serialization_alias`; `get_schema_from_model_field` uses `field_alias` depending on `mode`), `fastapi/dependencies/utils.py` (new `get_validation_alias()`, used in `_get_multidict_value`, `request_params_to_args`, `request_body_to_args`, `loc`), `fastapi/openapi/utils.py`, `fastapi/params.py`.
- **Strategy**: 1) Add the props in `_compat/v2.py`. 2) Create `get_validation_alias(field) = field.validation_alias or field.alias`. 3) Replace ALL uses of `field.alias` in read/validation/`loc`/titles with the helper (watch out for `convert_underscores`: compare against the validation alias, not against `name`). 4) Verify schema validation vs serialization.
- **Complexity**: High (6848 gold lines, 4 files, `test_patch` of 134k with hundreds of tests).
- **Blockers**: the `test_*_validation_alias_*` and `test_*_alias_and_validation_alias_*` families in `tests/test_request_params/{body,cookie,file,form,header,path,query}/` (e.g. `test_required_list_validation_alias_by_name`, `test_required_alias_and_validation_alias_by_alias`). Trap: mixing `alias` and `validation_alias`, and `AliasPath`/`AliasChoices` (unsupported).

### fastapi_14372 — Hashable `Depends()` / `Security()`
- **What it is**: workaround for external tools that hash these objects; no official support for extending internals.
- **What is missing (gold)**: `fastapi/params.py` + `fastapi/dependencies/utils.py`: `@dataclass(frozen=True)` on the results of `Depends()`/`Security()` and `dataclasses.replace(depends, dependency=type_annotation)`.
- **Strategy**: 1) Make the dataclasses frozen. 2) Replace the mutation with `dataclasses.replace`. 3) Run `tests/test_depends_hashable.py`.
- **Complexity**: Low (gold ~1000 lines, 2 files, 1 test).
- **Blockers**: `test_depends_hashable` (`tests/test_depends_hashable.py`). Trap: breaking dependency equality/cache when touching the dataclass.

### fastapi_14419 — Cache dependencies without scopes
- **What it is**: dependencies were cached by function + scopes; a dependency without scopes stayed tied to the parent's scope and was re-executed. Related to #9790 and discussion #6024.
- **What is missing (gold)**: `fastapi/dependencies/models.py` + `utils.py`: `own_oauth_scopes` / `parent_oauth_scopes`, `cached_property oauth_scopes` (joins preserving order), `_uses_scopes`, and the cache logic that distinguishes.
- **Strategy**: 1) Separate own vs inherited scopes. 2) Cache by function unless the dependency or its sub-deps use scopes. 3) Verify with the call-count tests.
- **Complexity**: High (gold 6222, cache with scope semantics).
- **Blockers**: `test_security_scopes_dependency_called_once`, `test_security_scopes_sub_dependency_caching` (`tests/test_security_scopes.py`, `tests/test_security_scopes_sub_dependency.py`). Trap: using a `set` (loses order) or over/under-caching.

### fastapi_14430 — Optional sequences with `X | None` syntax
- **What it is**: #14297 only accounted for one type of the union; with `UnionType` (PEP 604), `Optional[list[...]]` failed.
- **What is missing (gold)**: `fastapi/_compat/v2.py`: import `UnionType` from `fastapi.types` and check `origin_type is Union or origin_type is UnionType`.
- **Strategy**: 1) Reproduce with `list[str] | None`. 2) Add the `UnionType` branch. 3) Run `tests/test_compat.py`.
- **Complexity**: Low (gold ~1000 lines, 1 file, 3 tests).
- **Blockers**: `test_serialize_sequence_value_with_optional_list`, `test_serialize_sequence_value_with_optional_list_pipe_union`, `test_serialize_sequence_value_with_none_first_in_union`. Trap: only testing `typing.Optional` and not `|`; `None` order first.

### fastapi_14448 — `functools.wraps` + `partial` in dependencies and path ops
- **What it is**: combinations of decorators/wraps/partial (async and sync funcs, classes) broke detection. Extends @YuriiMotov's tests; touches #14444.
- **What is missing (gold)**: `fastapi/dependencies/utils.py` + `models.py`: helpers `_unwrapped_call()` (`inspect.unwrap(_impartial(call))`) and `_impartial()` (unwraps `partial`), used to detect coroutines/generators/classes.
- **Strategy**: 1) Centralize the unwrap in those two helpers. 2) Use them in async/gen detection and in `solve_dependencies`. 3) Test the matrix: sync/async × function/class × wraps/partial.
- **Complexity**: High (gold 5846, large combinatorics).
- **Blockers**: `test_class_dependency` (`tests/test_dependency_wrapped.py`, 11k of tests). Trap: `inspect.unwrap` on `partial` without unwrapping first; regressions in classes (see 14458).

### fastapi_14455 — OpenAPI: dedup OAuth2 scopes by scheme
- **What it is**: the same scheme with different scopes generated duplicate entries in `security`. Fixes #14454.
- **What is missing (gold)**: `fastapi/openapi/utils.py`: `operation_security_dict: Dict[str, List[str]]` that merges scopes by `security_name` preserving order.
- **Strategy**: 1) Group by scheme name. 2) Merge scopes without duplicates. 3) Compare the expected `test_openapi_schema`.
- **Complexity**: Low (gold 1374, 1 file).
- **Blockers**: `test_root`, `test_read_token`, `test_create_token`, `test_openapi_schema` (`tests/test_security_oauth2_authorization_code_bearer_scopes_openapi.py`). Trap: dedup with a `set` that reorders scopes.

### fastapi_14458 — Regression: class (not instance) with `__call__` as a dependency
- **What it is**: since 0.123.6, a class with a coroutine/generator `__call__` was detected incorrectly (the class was inspected as if it were the instance). Report in discussion #14452.
- **What is missing (gold)**: `fastapi/dependencies/models.py`: guards `if inspect.isclass(_unwrapped_call(self.call)): return False` in the three detections (coroutine/generator).
- **Strategy**: 1) Before `iscoroutinefunction`/`isgeneratorfunction`, short-circuit if it is a class. 2) Reuse `_unwrapped_call`. 3) Run `tests/test_dependency_class.py`.
- **Complexity**: Low (gold 1661, specific guards).
- **Blockers**: `test_class_dependency` (`tests/test_dependency_class.py`). Trap: inspecting `Clase.__call__` instead of the class; confusing class vs instance.

### fastapi_14459 — OAuth2 scopes in OpenAPI, corner cases
- **What it is**: a parent with scopes + a sub-dep without scopes (or the same scheme in another path op without scopes) ended up cached without scopes in the schema.
- **What is missing (gold)**: `models.py` (`SecurityRequirement`, `_is_security_scheme`, `_security_scheme`, `_security_dependencies`), `dependencies/utils.py`, `openapi/utils.py`.
- **Strategy**: 1) Mark which sub-deps are security schemes. 2) Prevent the OpenAPI cache from mixing variants with/without scopes. 3) Cover the 3 corner cases from the title, one at a time, comparing schemas.
- **Complexity**: High (gold 7266, 3 files, cache+OpenAPI interaction).
- **Blockers**: `test_read_with_oauth2_scheme`, `test_read_with_get_token`, `test_read_admin`, `test_openapi_schema` (2 files `test_security_oauth2_authorization_code_bearer_scopes_openapi*.py`). Trap: execution order hides the bug (contaminated cache).

### fastapi_14463 — OpenAPI duplicated `anyOf` with `responses` at the app level
- **What it is**: `responses={...}` with a `Union` of models + `content`/`examples` accumulated duplicate `$ref`s in `anyOf`.
- **What is missing (gold)**: `fastapi/openapi/utils.py`: `import copy` + `process_response = copy.deepcopy(additional_response)` before mutating.
- **Strategy**: 1) Reproduce the issue's MRE. 2) Deep-copy the additional response per iteration. 3) Run the schema test.
- **Complexity**: Low (gold 647).
- **Blockers**: `test_openapi_schema` (`tests/test_additional_responses_union_duplicate_anyof.py`). Trap: shallow copy (the `anyOf` persists); mutating the user's dict.

### fastapi_14479 — Better message for a mistyped query param
- **What it is**: since #12942 an invalid annotation crashed with a bare `AssertionError`; now the assert says which param and which types are valid.
- **What is missing (gold)**: `fastapi/dependencies/utils.py`: `f"Query parameter {param_name!r} must be one of the supported types"`.
- **Strategy**: 1) Locate the assert. 2) Add the message with the param name. 3) Run `tests/test_invalid_sequence_param.py`.
- **Complexity**: Low (gold 417).
- **Blockers**: `test_invalid_sequence`, `test_invalid_tuple`, `test_invalid_dict`, `test_invalid_simple_dict`. Trap: changing the exception type instead of the message (the tests match the message).

### fastapi_14482 — `arbitrary_types_allowed=True`
- **What it is**: arbitrary types (#14184, #14483) broke the creation of the field/model.
- **What is missing (gold)**: `fastapi/_compat/v2.py`: rebuild with `TypeAdapter`/`create_model`, passing `annotation + metadata + field_info` and `config`.
- **Strategy**: 1) Reproduce with the issue's arbitrary type. 2) Build the adapter with `annotated_args`. 3) Run `tests/test_arbitrary_types.py`.
- **Complexity**: Medium (gold 2520, 1 file, pydantic edge).
- **Blockers**: `test_get`, `test_typeadapter`, `test_openapi_schema` (`tests/test_arbitrary_types.py`). Dependency: pydantic version (`TypeAdapter` behavior).

### fastapi_14485 — Stringified annotations with `if TYPE_CHECKING`
- **What it is**: dependencies with a return annotation under `TYPE_CHECKING` (#14464, #14484, follows #11355) threw `NameError` in `inspect.signature`.
- **What is missing (gold)**: `fastapi/dependencies/utils.py`: `get_typed_signature()` / `_get_signature()` with `inspect.signature(call, eval_str=True)` and fallback to `inspect.signature(call)` on `NameError`.
- **Strategy**: 1) Call with `eval_str=True`. 2) Catch only `NameError` and retry without evaluating. 3) Run `tests/test_stringified_annotation_dependency.py`.
- **Complexity**: Low (gold 1501).
- **Blockers**: `test_get`, `test_openapi_schema` (`tests/test_stringified_annotation_dependency.py`). Trap: swallowing other exceptions or always evaluating (breaks `TYPE_CHECKING`).

### fastapi_14487 — Docs: do not log the raw validation error
- **What it is**: docs only; the example re-raised `str(exc)` and leaked info. Now it builds a field-by-field message.
- **What is missing (gold)**: `docs_src/handling_errors/tutorial004.py`: `validation_exception_handler` that iterates `exc.errors()` (`loc`, `msg`) and returns `PlainTextResponse(..., 400)`.
- **Strategy**: 1) Edit only the tutorial. 2) Do not touch runtime. 3) Run `tests/test_tutorial/test_handling_errors/test_tutorial004.py`.
- **Complexity**: Low (gold 629, docs).
- **Blockers**: `test_get_validation_error`, `test_get_http_error`. Trap: touching `fastapi/exception_handlers.py` (not needed).

### fastapi_14492 — Docs: license identifier
- **What it is**: docs typo, `MIT` → `Apache-2.0`.
- **What is missing (gold)**: `docs_src/metadata/tutorial001_1_py39.py`: `"identifier": "Apache-2.0"`.
- **Strategy**: Change the string and run `tests/test_tutorial/test_metadata/test_tutorial001_1.py::test_openapi_schema`.
- **Complexity**: Low (gold 248).
- **Blockers**: the tutorial's exact `test_openapi_schema`. Trap: none, but the snapshot is literal.

### fastapi_14512 — Discriminated union inside `Annotated[..., Body()]`
- **What it is**: a tagged union with `discriminator` inside `Annotated` (#14495, #14508) was not resolved.
- **What is missing (gold)**: `fastapi/_compat/v2.py`: attribute normalization (`default`, `alias`, `validation_alias`, etc., with `_Attrs` and a TODO for pydantic < 2.12.3).
- **Strategy**: 1) Reproduce with the snippet from #14495. 2) Propagate the `discriminator` when creating the body field. 3) Run `tests/test_union_body_discriminator_annotated.py`.
- **Complexity**: Medium (gold 2723).
- **Blockers**: `test_union_body_discriminator_assignment`, `test_union_body_discriminator_annotated`, `test_openapi_schema`. Trap: works without `Annotated` and fails with `Annotated` (double wrapping).

### fastapi_14583 — Warnings when using `pydantic.v1`
- **What it is**: a step prior to dropping v1: it warns on params/return/response.
- **What is missing (gold)**: `fastapi/dependencies/utils.py` + `fastapi/routing.py`: `warnings.warn("pydantic.v1 is deprecated ... {param_name}: {type_annotation!r}", DeprecationWarning, stacklevel=5)` when the field is `may_v1.ModelField`.
- **Strategy**: 1) Detect the v1 field. 2) Warn with the correct `stacklevel`. 3) Run the warning tests (note that 14605 changes the category afterwards).
- **Complexity**: Medium (gold 2731, `test_patch` of 57k shared with v1).
- **Blockers**: `test_warns_pydantic_v1_model_in_endpoint_param`, `test_warns_pydantic_v1_model_in_return_type`, `test_warns_pydantic_v1_model_in_response_model`, `test_header_params_none`, `test_cookie_params`. Trap: wrong `stacklevel` or warning twice; not to be confused with `FastAPIDeprecationWarning` (that is 14605).

### fastapi_14605 — Its own `FastAPIDeprecationWarning`
- **What it is**: `DeprecationWarning` is ignored by default (see sethmlarson.dev); it creates its own warning and uses it on deprecated paths (v1, `regex`, `example`).
- **What is missing (gold)**: `fastapi/exceptions.py` (`class FastAPIDeprecationWarning(UserWarning)`), plus `dependencies/utils.py`, `openapi/utils.py`, `params.py`, `routing.py`, `temp_pydantic_v1_params.py`, `utils.py` changing `category=`.
- **Strategy**: 1) Create the class. 2) Replace categories in all deprecated warns. 3) Update asserts with `pytest.warns(FastAPIDeprecationWarning)`.
- **Complexity**: High (gold 7836, 7 files, cross tests).
- **Blockers**: `test_query_regex_deprecation_warning`, `test_body_regex_deprecation_warning`, `test_query_example_deprecation_warning`, `test_body_example_deprecation_warning`, `test_body_repr`. Trap: mixing with a bare `DeprecationWarning` (14583) or `UserWarning`.

### fastapi_14609 — Drop `pydantic.v1` support
- **What it is**: the big one of the block: the v1 shim is removed; using `pydantic.v1` raises an error. Touches 20 files.
- **What is missing (gold)**: `fastapi/_compat/{__init__,main,may_v1,model_field,shared,v1,v2}.py`, `datastructures.py`, `dependencies/utils.py`, `encoders.py`, `exceptions.py`, `openapi/{models,utils}.py`, `param_functions.py`, `params.py`, `routing.py`, `temp_pydantic_v1_params.py`, `utils.py` (+ pv1 docs). Symbols: `get_cached_model_fields`, `copy_field_info`, `create_body_model`, `is_scalar(_sequence)_field`, `is_bytes(_sequence)_field`, etc. become v2-only.
- **Strategy**: 1) Do not implement it from scratch: apply the gold file by file and compile after each one. 2) Delete `may_v1`/`v1` imports and pv1 branches in tests. 3) Run in this order: `test_compat`, `test_compat_params_v1`, `test_jsonable_encoder`, `test_filter_pydantic_sub_model`, `test_datetime_custom_encoder`. 4) Assume that any `is_pv1_*` helper disappears.
- **Complexity**: High (gold 103371, 20 files; the biggest of the block).
- **Blockers**: `test_model_field_default_required`, `test_v1_plain_validator_function`, `test_is_model_field`, `test_get_model_config`, `test_is_pv1_scalar_field`, `test_get_model_fields_cached`, `test_serialize_sequence_value_with_none_first_in_union` + families `test_query_params_*`, `test_body_param*`, `test_form_data_*`, `test_upload_*`. Trap: residual v1 imports; tests that expect a warning (14583/14605) now expect an error.

### fastapi_14616 — `Json[list[str]]` in Form/Query/Header/Cookie
- **What it is**: `Json[T]` with `T` a sequence (#10997) was treated as a sequence and did `getlist()`, wrapping the JSON in a list → `TypeError: JSON input should be string, bytes or bytearray`.
- **What is missing (gold)**: `fastapi/dependencies/utils.py`: `_is_json_field()` (`type(item) is Json` in `metadata`) and skip the sequence branch in `_get_multidict_value` when it is JSON.
- **Strategy**: 1) Reproduce `Form(Json[list[str]])` by sending a JSON string. 2) Add the guard. 3) Run `tests/test_json_type.py`.
- **Complexity**: Low (gold 1213).
- **Blockers**: `test_form_json_list`, `test_query_json_list`, `test_header_json_list`, `test_cookie_json_list`. Trap: checking `isinstance` instead of `type(...) is Json` (false positives with subclasses).

### fastapi_14786 — Strip whitespace in `Authorization` credentials
- **What it is**: RFC 6750 allows `1*SP` between `Bearer` and the token, but the token (`b64token`) does not include whitespace; the `param` came back with spaces.
- **What is missing (gold)**: `fastapi/security/utils.py`: `return scheme, param.strip()`.
- **Strategy**: One line + run `test_security_http_base*` and `test_security_oauth2_authorization_code_bearer*`.
- **Complexity**: Low (gold 304, the smallest runtime one).
- **Blockers**: `test_security_http_base`, `test_security_http_base_with_whitespaces`, `test_security_http_base_no_credentials`, `test_token`, `test_token_with_whitespaces`, `test_openapi_schema`. Trap: stripping the `scheme` too or breaking the no-credentials case.

### fastapi_14791 — OpenAPI schema of `ValidationError` with `input` and `ctx`
- **What it is**: the schema was outdated vs pydantic v2 (#10787); `input` (the value that failed) and `ctx` were missing.
- **What is missing (gold)**: `fastapi/openapi/utils.py`: `validation_error_definition` adds `"input": {"title": "Input"}` and `"ctx": {"title": "Context", "type": "object"}`.
- **Strategy**: 1) Edit the dict. 2) Since the global schema changes, run the WHOLE `test_patch` (28 files, all `test_openapi_schema`/`test_openapi`). There is no shortcut.
- **Complexity**: Medium (gold 353 but an enormous blast radius: 18k of tests).
- **Blockers**: `test_openapi_schema` (×25) and `test_openapi` in `test_annotated`, `test_application`, `test_dependency_duplicates`, `test_forms_single_param`, etc. Trap: literal snapshot — any extra/missing key breaks 28 files.

### fastapi_14794 — `Response` as a dependency annotation
- **What it is**: ` Annotated[Response, Depends(modify_response)]` (#10127) died with `AssertionError: Cannot specify Depends for type Response`.
- **What is missing (gold)**: `fastapi/dependencies/utils.py` in `analyze_param()`: `if depends is None and lenient_issubclass(...)` — the special handling of `Response`/`Request`/`BackgroundTasks` only when there is NO explicit `Depends`.
- **Strategy**: 1) Move the guard before the special-casing. 2) If there is `Depends`, let `Depends` win. 3) Run `tests/test_response_dependency.py` (7 tests, includes chains).
- **Complexity**: Low (gold 871).
- **Blockers**: `test_response_with_depends_annotated`, `test_response_with_depends_default`, `test_response_without_depends`, `test_response_dependency_chain`, `test_response_dependency_returns_different_response_instance`, `test_request_with_depends_annotated`, `test_background_tasks_with_depends_annotated`. Trap: inverting the order and breaking direct injection of `Response`.

### fastapi_14851 — Re-implement `on_event` for Starlette compat
- **What it is**: Starlette removes `on_event`; FastAPI re-implements it with lifespan, with backwards-compat. Unblocks the future interface.
- **What is missing (gold)**: `fastapi/routing.py`: `_AsyncLiftContextManager`, `_wrap_gen_lifespan_context`, `_merge_lifespan_context`, `_DefaultLifespan`, `add_event_handler`, bridging `_startup`/`_shutdown`.
- **Strategy**: 1) Implement the lifespan shim with `AsyncExitStack`/`asynccontextmanager`. 2) Register old handlers (`@app.on_event("startup")`) on the lifespan. 3) Test sync/async × startup/shutdown × gen.
- **Complexity**: High (gold 6843, lifespan state, easy deadlock).
- **Blockers**: `test_router_async_shutdown_handler`, `test_router_sync_generator_lifespan`, `test_router_async_generator_lifespan` (`tests/test_router_events.py`). Trap: double execution of handlers; mixing with 14873.

### fastapi_14873 — `on_startup`/`on_shutdown` as `APIRouter` params
- **What it is**: fix for the comment on #14851: `APIRouter.__init__` set `on_startup` before calling super and Starlette no longer supports it → they were lost.
- **What is missing (gold)**: `fastapi/routing.py`: store locally `self.on_startup = [] if on_startup is None else list(on_startup)` (same for shutdown) with ref to starlette#3117.
- **Strategy**: 1) Copy the lists in `__init__` (no mutable aliases). 2) Wire them to the local lifespan. 3) Run the test with `FastAPI(on_startup=[s_start])` + `/health`.
- **Complexity**: Low (gold 1623).
- **Blockers**: `test_startup_shutdown_handlers_as_parameters` (`tests/test_router_events.py`). Trap: mutable default `[]`; assuming Starlette handles it.

### fastapi_14953 — JSON Schema for `bytes`: `contentMediaType` instead of `format: binary`
- **What it is**: OpenAPI 3.1 aligns with JSON Schema: `contentMediaType: application/octet-stream`, not `format: binary`.
- **What is missing (gold)**: `fastapi/_compat/v2.py` (custom `GenerateJsonSchema.bytes_schema`), `fastapi/datastructures.py`, plus `docs_src/json_base64_bytes/tutorial001_py310.py` and `scripts/playwright/.../image01.py`.
- **Strategy**: 1) Override `bytes_schema` in the generator. 2) Update the tutorial + playwright script together. 3) Run `test_json_base64_bytes` + the `test_*_schema` families from `test_request_params/test_file/`.
- **Complexity**: Medium (gold 4315, 4 files, snapshots).
- **Blockers**: `test_post_data`, `test_get_data`, `test_post_data_in_out`, `test_list_schema`, `test_*_alias*_schema` (file params), `test_openapi_schema` (×8 tutorials). Trap: leaving `format: binary` in some tutorial; validation that requires real `bytes`.

### fastapi_14962 — Serialize JSON with Pydantic (Rust) when there is a return type/response model
- **What it is**: fast-path: if there is a return annotation or response model, it serializes with pydantic instead of `json.dumps`.
- **What is missing (gold)**: `fastapi/_compat/v2.py` (`serialize_json` with `include/exclude`), `fastapi/routing.py` (choose the path), `docs_src/custom_response/tutorial010_py310.py`.
- **Strategy**: 1) Implement `serialize_json`. 2) In routing, use it only when there is a return type/response model; if `default_response_class` is explicit, respect `json_dumps`. 3) Measure with `test_dump_json_fast_path`.
- **Complexity**: Medium (gold 4222).
- **Blockers**: `test_default_response_class_skips_json_dumps`, `test_explicit_response_class_uses_json_dumps`, `test_get_custom_response`, `test_openapi_schema`. Trap: using the fast-path without a response model (changes format) — goes with 14964.

### fastapi_14964 — Deprecate `ORJSONResponse` / `UJSONResponse`
- **What it is**: consequence of 14962: a custom response is no longer needed for performance; they are removed from `fastapi[all]`.
- **What is missing (gold)**: `fastapi/responses.py`: `@deprecated("UJSONResponse is deprecated, FastAPI now serializes ...")` + `FastAPIDeprecationWarning`.
- **Strategy**: 1) Decorate both classes. 2) Remove extras from packaging. 3) Run `test_deprecated_responses` + `test_orjson_response_class`.
- **Complexity**: Medium (gold 3966, packaging decision).
- **Blockers**: `test_orjson_response_returns_correct_data`, `test_orjson_response_emits_deprecation_warning`, `test_ujson_response_returns_correct_data`, `test_ujson_response_emits_deprecation_warning`, `test_orjson_non_str_keys`. Trap: the tests require OK data + warning at the same time; forgetting `typing_extensions.deprecated`.

### fastapi_14978 — `strict_content_type` for JSON
- **What it is**: new feature: opt-in (`False` by default) that rejects JSON without `Content-Type`; app→router→nested route inheritance.
- **What is missing (gold)**: `fastapi/applications.py` + `fastapi/routing.py` (flag, 422/415-ish check, inheritance), `docs_src/strict_content_type/tutorial001_py310.py` (`Item`, `create_item`).
- **Strategy**: 1) Thread the flag app→router→route. 2) Reject a JSON body without content-type only in strict. 3) Test the 12-test matrix: default-strict vs lax × app/nested router.
- **Complexity**: High (gold 7864, inheritance semantics).
- **Blockers**: `test_default_strict_rejects_no_content_type`, `test_default_strict_accepts_json_content_type`, `test_lax_accepts_no_content_type`, `test_strict_inner_on_lax_app_rejects_no_content_type`, `test_default_inner_inherits_lax_from_app`, `test_lax_outer_on_strict_app_accepts_no_content_type` (+6 more). Trap: inverted default (it must be strict by default in the tests); inheritance backwards.

### fastapi_14986 — OpenAPI/Swagger: `root_path` + HTML escaping
- **What it is**: do not persist a foreign `root_path` in `servers` (malicious proxy with `x-forwarded-*`) + escape HTML in Swagger UI params/init-oauth.
- **What is missing (gold)**: `fastapi/applications.py` (per-request schema: if `root_path` is not in `server_urls`, `schema = dict(schema); schema["servers"] = [{"url": root_path}] + ...`, without mutating config), `fastapi/openapi/docs.py` (`_html_safe_json`).
- **Strategy**: 1) Never mutate `self.servers`; copy per request. 2) Escape all JSON injected into HTML. 3) Run `test_openapi_cache_root_path` + `test_swagger_ui_escape`.
- **Complexity**: Medium (gold 2622, security).
- **Blockers**: `test_root_path_does_not_persist_across_requests`, `test_multiple_different_root_paths_do_not_accumulate`, `test_legitimate_root_path_still_appears`, `test_configured_servers_not_mutated`, `test_init_oauth_html_chars_are_escaped`, `test_swagger_ui_parameters_html_chars_are_escaped`, `test_normal_init_oauth_still_works`. Trap: caching the schema with the `root_path` stuck on; double-escape.

### fastapi_15023 — Docs: streams with `yield`
- **What it is**: docs only for the streaming tutorial (without `async yield from`).
- **What is missing (gold)**: `docs_src/stream_data/tutorial002_py310.py`: `stream_image_no_async_yield_from` with `for chunk in image_file: yield chunk`.
- **Strategy**: Edit the tutorial and run `tests/test_tutorial/test_stream_data/test_tutorial002.py::test_openapi_schema`.
- **Complexity**: Low (gold 1480, docs).
- **Blockers**: the tutorial's `test_openapi_schema`. Trap: no technical one; do not touch runtime.

### fastapi_15030 — Server-Sent Events (`EventSourceResponse`)
- **What it is**: big feature: SSE with `fastapi/sse.py`, sync/async generators, models, `data/event/id/retry`, `_serialize_sse_item` serialization, plus OpenAPI/routing and 5 tutorials.
- **What is missing (gold)**: new `fastapi/sse.py` (`EventSourceResponse`, `_async_stream_sse`, `_producer`, `_serialize_data/item/sse_item`), `fastapi/responses.py`, `fastapi/routing.py`, `fastapi/openapi/utils.py`, `docs_src/server_sent_events/tutorial001–005_py310.py`.
- **Strategy**: 1) Implement `sse.py` first and its unit tests (`test_sse.py`). 2) Then wire routing (detect the SSE generator) and OpenAPI. 3) Finally the 5 tutorials. 4) Validate `post_method_sse`, mixed plain/SSE events, `string_data_json_encoded`.
- **Complexity**: High (gold 25624, 9 source+docs files, 37k of tests).
- **Blockers**: `test_async_generator_with_model`, `test_sync_generator_with_model`, `test_async_generator_no_annotation`, `test_sync_generator_no_annotation`, `test_dict_items`, `test_post_method_sse`, `test_sse_events_with_fields`, `test_mixed_plain_and_sse_events`, `test_string_data_json_encoded`, `test_server_sent_event_null_id_rejected`, `test_server_sent_event_negative_retry_rejected`, `test_server_sent_event_float_retry_rejected`. Trap: field validation (continues in 15588); negative/float `retry`; `id` with null.

### fastapi_15280 — `@app.vibe()`
- **What it is**: endpoint decorator `vibe`/`ai_vibes` (+ `websocket_route`) with a minimal test.
- **What is missing (gold)**: `fastapi/applications.py` (`ai_vibes`, `vibe`, `websocket_route`), `docs_src/vibe/tutorial001_py310.py`.
- **Strategy**: 1) Add the decorator mirroring `get/post` but on the vibe registration. 2) Run `tests/test_vibe.py`.
- **Complexity**: Low (gold 2605 but almost all docs; 1 test).
- **Blockers**: `test_vibe_raises` (`tests/test_vibe.py`). Trap: over-engineering; the test only requires that it fails properly.

### fastapi_15588 — Validate SSE fields
- **What it is**: hardens 15030: `event`/`id`/etc. single-line (no `\r`/`\n`), valid `id`.
- **What is missing (gold)**: `fastapi/sse.py`: `_check_id_no_null`, `_check_single_line`, `_check_event_single_line`, `_check_id_valid`.
- **Strategy**: 1) Validate at event construction, not at serialization. 2) `ValueError("SSE '{field}' must be a single line")`. 3) Run `test_sse.py`.
- **Complexity**: Low (gold 1825).
- **Blockers**: `test_server_sent_event_null_id_rejected`, `test_server_sent_event_single_line_fields_reject_newlines`, `test_server_sent_event_negative_retry_rejected`. Trap: validating late (already streamed); message different from the expected one.

### fastapi_15589 — Headers with `convert_underscores=True` do not accept `_`
- **What it is**: with conversion (default), `x_token`→`x-token`; the bug also accepted the header with `_` as an extra.
- **What is missing (gold)**: `fastapi/dependencies/utils.py`: `processed_keys.add(get_validation_alias(field))` for the converted form AND the original alias.
- **Strategy**: 1) Mark both keys as processed. 2) Verify the hyphenated preference and rejection of the underscore. 3) Run `test_query_cookie_header_model_extra_params`.
- **Complexity**: Low (gold 635).
- **Blockers**: `test_query_pass_extra_list`, `test_header_pass_extra_single`, `test_header_model_prefers_hyphenated_header_with_convert_underscores`, `test_header_model_rejects_underscore_header_with_convert_underscores`, `test_cookie_pass_extra_list`. Trap: interacts with `get_validation_alias` (14371) — order of application.

### fastapi_15661 — Automate `prepare_release`
- **What it is**: the only non-runtime one of the block: `prepare_release.py` script (typer) + its own tests. Done with Codex/GPT-5.5.
- **What is missing (gold)**: `scripts/prepare_release.py`: `parse_version`, `get_current_version`, `bump_version`, `update_version_file`, `update_release_notes`, `get_release_notes_body`, `prepare`.
- **Strategy**: 1) Implement semver parse/bump. 2) `update_version_file` requires a newer version. 3) `update_release_notes` rejects an existing version and requires a non-empty section. 4) Support CLI env vars.
- **Complexity**: Medium (gold 6966 but isolated, no runtime).
- **Blockers**: `test_bump_version`, `test_update_version_file`, `test_update_version_file_requires_newer_version`, `test_update_release_notes`, `test_update_release_notes_rejects_existing_version`, `test_get_release_notes_body_with_dated_heading`, `test_get_release_notes_body_with_plain_heading`, `test_get_release_notes_body_allows_non_version_h2_content`, `test_get_release_notes_body_requires_version_section`, `test_get_release_notes_body_requires_non_empty_section`, `test_cli_updates_configured_files`, `test_cli_accepts_env_vars` (`tests/test_prepare_release.py`). Trap: headings with/without a date; non-version `h2` allowed.

### fastapi_15745 — Preserve `APIRouter`/`APIRoute` instances on include
- **What it is**: `include_router` cloned everything; now it preserves instances (unblocks custom route classes, openapi cache, `url_path_for`). Supersedes #4794. The riskiest one along with 14609.
- **What is missing (gold)**: `fastapi/applications.py`, `fastapi/openapi/utils.py`, `fastapi/routing.py`: `_get_api_route_for_openapi`, `_get_fastapi_scope`, `_get_scope_effective_route_context`, `_get_scope_included_router`, `_populate_api_route_state`, `APIRoute.handle`, `_RouterIncludeContext`, `_openapi_routes_version` versioning.
- **Strategy**: 1) Do not re-implement: port the gold function by function. 2) Verify in order: `test_custom_route_class` → `test_router_include_context` (cycles, nested includes, live routes). 3) Watch the OpenAPI cache after `live_route_addition`.
- **Complexity**: High (gold 63497, the largest live refactor).
- **Blockers**: `test_get_path`, `test_route_classes`, `test_openapi_schema`, `test_router_include_context_matches_flattened_include_metadata`, `test_live_route_addition_uses_include_metadata_for_runtime_and_openapi`, `test_openapi_cache_updates_after_live_route_addition`, `test_nested_router_added_after_parent_inclusion_is_live`, `test_repeated_deep_inclusions_handle_all_concrete_paths`, `test_url_path_for_uses_effective_context_for_live_included_route`, `test_url_path_for_uses_distinct_repeated_inclusion_contexts`, `test_indirect_router_inclusion_cycles_are_rejected`, `test_original_api_route_subclass_instance_is_called_after_inclusion`. Trap: inclusion cycles; effective vs original context (continues in 15763/15785).

### fastapi_15763 — Empty path in a router without a prefix
- **What it is**: bug from 15745: validation saw the original path instead of the effective one and rejected `""`.
- **What is missing (gold)**: `fastapi/routing.py`: iterate `_iter_routes_with_context` and validate against `route_context.starlette_route.path` (effective), with fallback to `route.path`.
- **Strategy**: 1) Reproduce #15762. 2) Use the effective path in validation. 3) Run `test_router_include_context.py`.
- **Complexity**: Low (gold 1159).
- **Blockers**: `test_no_prefix_include_validation_sees_effective_api_route_path`, `test_no_prefix_include_validation_sees_effective_starlette_route_path`, `test_no_prefix_include_validation_rejects_empty_effective_api_route_path`, `test_apirouter_matches_fallback_without_include_context`. Trap: `None` vs `""` (empty is valid only if the effective one is not empty).

### fastapi_15785 — Public `iter_route_contexts()`
- **What it is**: exposes the contexts from 15745 for power-users (e.g. Jupyverse, which read `router.routes`). Discussion #15782.
- **What is missing (gold)**: `fastapi/routing.py` (`RouteContext`, `original_route`, `_effective_route`, `path`, `path_format`, `name`, `methods`, `endpoint`, `iter_route_contexts`, `_iter_routes_with_context`) + `fastapi/openapi/utils.py` (accepts `Sequence[BaseRoute | RouteContext]` in routes and webhooks).
- **Strategy**: 1) Implement `RouteContext` with `__getattr__` delegating to the effective one. 2) `get_openapi` must accept a mix of routes and contexts. 3) Run `test_router_include_context.py`.
- **Complexity**: Medium (gold 5265, new public API).
- **Blockers**: `test_iter_route_contexts_returns_direct_route_context`, `test_iter_route_contexts_supports_nested_conflict_detection`, `test_get_openapi_accepts_filtered_route_contexts_with_effective_paths`, `test_get_openapi_accepts_webhook_route_contexts`, `test_router_include_context_matches_flattened_include_metadata`. Trap: filtering contexts breaks nested conflict detection.

### fastapi_15800 — `app.frontend("/", directory="dist")`
- **What it is**: serves SPAs: `frontend()` on app and router, `_FrontendStaticFiles`, low-priority routes, path resolution, index fallback.
- **What is missing (gold)**: `fastapi/applications.py` + `fastapi/routing.py` (`frontend`, `api_route`, `_RouteWithPath`, `_get_fastapi_scope`, `_update_scope`, `_get_scope_effective_route_context`, `path_for`, `effective_low_priority_routes`, `_build_effective_context`, `_normalize_frontend_path`, `_join_frontend_paths`, `_frontend_path_specificity`, `_get_resolved_absolute_path`, `_FrontendStaticFiles`) + 6 tutorials `docs_src/frontend/`.
- **Strategy**: 1) Static files with fallback to index. 2) Normal routes win over frontend on a partial match. 3) Low-priority cache with invalidation on including routers. 4) Run the full `tests/test_frontend.py` (12 tests).
- **Complexity**: High (gold 28982).
- **Blockers**: `test_frontend_exact_prefix_path_serves_index`, `test_apirouter_frontend_with_router_prefix_and_frontend_subpath`, `test_frontend_fallback_rejects_invalid_fallback`, `test_index_fallback_ignores_invalid_q_value`, `test_frontend_static_files_lookup_errors`, `test_frontend_route_group_helpers`, `test_included_low_priority_routes_cache_is_reused`, `test_low_priority_api_route_handles_with_context`, `test_included_low_priority_api_route_handles_with_context`, `test_normal_route_partial_match_wins_before_frontend`, `test_basic_file_serving`. Trap: path traversal; invalid `q` in fallback; stale cache after `include_router`.

### fastapi_5077 — Wraps + forward refs
- **What it is**: `functools.wraps` copies `__annotations__` with strings; `get_typed_signature` computed `globalns` from the wrapper and lost the namespace (fixes #5065, mirrors `typing.get_type_hints`).
- **What is missing (gold)**: `fastapi/dependencies/utils.py`: `unwrapped = inspect.unwrap(call); globalns = getattr(unwrapped, "__globals__", {})`.
- **Strategy**: 1) Unwrap before resolving hints. 2) Use the unwrapped globals. 3) Run `test_wrapped_method_forward_reference`.
- **Complexity**: Low (gold 1017).
- **Blockers**: `test_wrapped_method_type_inference` (`tests/test_wrapped_method_forward_reference.py` + `tests/forward_reference_type.py`). Trap: `functools.wraps` without a real `__wrapped__`.

### fastapi_5624 — Security scopes must not propagate upward
- **What it is**: fixes #5623: the sub-dependable's scopes contaminated the parent.
- **What is missing (gold)**: `fastapi/dependencies/utils.py`: `use_security_scopes = use_security_scopes + list(param_details.depends.scopes)` only downward.
- **Strategy**: 1) Propagate scopes parent→child, never the other way. 2) Run `test_security_scopes_dont_propagate`.
- **Complexity**: Low (gold 639).
- **Blockers**: `test_security_scopes_dont_propagate`. Trap: aliasing of mutable lists (use `+ list(...)`, not `extend` on the parent's).

### fastapi_9425 — `None` (stringified) as the return of a bodiless
- **What it is**: fixes #9424: an annotation exactly `"None"` must resolve to `None` for 204 No Content.
- **What is missing (gold)**: `fastapi/dependencies/utils.py`: `if annotation is type(None): return None` in the resolution.
- **Strategy**: 1) account for the string case `"None"` → `type(None)`. 2) Run `test_return_none_stringified_annotations`.
- **Complexity**: Low (gold 413, the smallest along with 14479).
- **Blockers**: `test_no_content`. Trap: confusing `None` with `"None"` in other positions; it is only valid as the exact return.

### fastapi_9555 — Wrapped deps (cache/coroutine)
- **What it is**: uses the unwrapped call in `solve_dependencies` to decide coroutine/generator; motivates the use of `functools.cache` in settings (the `@cache` caches the coroutine itself).
- **What is missing (gold)**: `fastapi/dependencies/models.py`: `cached_property _unwrapped_call` (`inspect.unwrap(self.call)`), used in `isgeneratorfunction` and `getattr(..., "__call__")`.
- **Strategy**: 1) Add the `cached_property`. 2) Replace the direct inspections. 3) Run `test_dependency_wrapped`.
- **Complexity**: Low (gold 1832).
- **Blockers**: `test_class_dependency` (`tests/test_dependency_wrapped.py`). Trap: `cache` on async without unwrap (precursor of 14448/14458).

### fastapi_9753 — `functools.partial` as dependables
- **What it is**: discussion #9744: `partial` worked on plain functions but not on async/classes with `__call__`.
- **What is missing (gold)**: `fastapi/dependencies/models.py`: `unwrapped = inspect.unwrap(self.call); if isinstance(unwrapped, partial): unwrapped = unwrapped.func`.
- **Strategy**: 1) After unwrap, take `partial` apart down to `func`. 2) Combine with `_unwrapped_call` (9555). 3) Run `test_dependency_partial` (+ renamed `test_dependency_class`).
- **Complexity**: Low (gold 789).
- **Blockers**: `test_dependency_types_with_partial` (`tests/test_dependency_partial.py`). Trap: nested `partial`s; `partial` of a class vs of an async function.

---

## Aggregate table

### Complexity distribution (44 tasks)

| Complexity | N | Tasks |
|---|---|---|
| High | 11 | 14371, 14419, 14448, 14459, 14605, 14609, 14851, 14978, 15030, 15745, 15800 |
| Medium | 10 | 14482, 14512, 14583, 14791, 14953, 14962, 14964, 14986, 15661, 15785 |
| Low | 23 | 14372, 14430, 14455, 14458, 14463, 14479, 14485, 14487, 14492, 14616, 14786, 14794, 14873, 15023, 15280, 15588, 15589, 15763, 5077, 5624, 9425, 9555, 9753 |

### Top 5 blockers of the block

| # | Blocker | Affected Tasks |
|---|---|---|
| 1 | Literal `test_openapi_schema` / `test_openapi` snapshots (any extra/missing key breaks everything) | 14371, 14455, 14459, 14463, 14791, 14953, 14962, 15745, 15785 + tutorials (14487, 14492, 15023) |
| 2 | `alias` vs `validation_alias` (+ `convert_underscores`, `loc`, schema titles) | 14371, 15589, 14512 |
| 3 | Dependency caching and propagation + scopes/security schemes | 14419, 14459, 5624, 14372 (hash/equality) |
| 4 | `inspect.unwrap` / `partial` / `wraps` / class-vs-instance in async/gen detection | 14448, 14458, 9555, 9753, 5077, 14485, 9425 |
| 5 | `pydantic.v1` deprecation/removal changes (warnings → `FastAPIDeprecationWarning` → error) | 14583, 14605, 14609 (with blast radius to `test_compat*`, `test_jsonable_encoder`, `test_filter_pydantic_sub_model`) |

Mentions near the top: lifespan/`on_event` + `on_startup/on_shutdown` (14851, 14873), SSE + field validation (15030, 15588), `include_router`/effective contexts/low-priority/`frontend` (15745, 15763, 15785, 15800), `strict_content_type` and inheritance (14978), `root_path`/XSS (14986), fast-path serialization + orjson/ujson deprecation (14962, 14964), `bytes`/`contentMediaType` (14953), `Response`-as-dependency (14794), `Json[list]` (14616), `Authorization.strip()` (14786), `UnionType` PEP 604 (14430), discriminated `Union` in `Annotated` (14512), `arbitrary_types` (14482), invalid query message (14479), release script (15661), `@app.vibe()` (15280).
