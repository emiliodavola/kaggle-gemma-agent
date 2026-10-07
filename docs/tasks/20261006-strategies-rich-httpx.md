---
Date: 2026-10-06
Genre: task digest
Status: current
Scope: Strategy and complexity for the rich_* tasks plus httpx_3672 (49 tasks); no runs/results were reviewed.
Source of truth: data/raw/tasks.jsonl; read 2026-10-06.
Limits: regenerable snapshot of the public task corpus; no random sampling.
---

# Strategies: rich_* segment + httpx_3672 (49 tasks)

Single source: `data/raw/tasks.jsonl` (fields `problem_statement`, `patch`, `test_patch`). Neither `runs/` nor `results/` were reviewed.
Date: 2026-10-06. Language: English.

## Complexity criterion (applies to the whole doc)

- **Low**: 1–5 line fix in a single module, cause localized in the `problem_statement`, test that leads straight to the point.
- **Medium**: change in 1–3 files with non-trivial logic (wrapping, styles, regex, env vars, segment splitting); requires reproducing rendering or reasoning about the interaction between modules.
- **High**: architectural or multi-module change with broad regression risk (duplicated parser+pool+server, unicode tables, import-time perf, PEP 657). Requires a broad verification strategy, not just the new test.

## Per-task summaries

### httpx_3672 — Server connection handling (encode/httpx, `4acf5c2c`)
- **What it is**: server-side keep-alive connection handling in the HTTP parser (`src/httpx/_parsers.py` + mirror `src/ahttpx/_parsers.py`, plus `_pool.py`/`_server.py`/`_network.py`).
- **What is missing**: add `HTTPParser.keep_alive`/`is_keepalive()`, rename `complete()` → `reset()` with a bool return, always read the request through to completion on keep-alives, close streams when leaving the server, and do not raise `KeyboardException` on exit.
- **Strategy**: 1) Read `_parsers.py` (state machine `send_state`/`recv_state`). 2) Rename `complete` → `reset` returning `False` (closed) / `True` (reusable) and reset states according to `Mode.CLIENT/SERVER`. 3) Add `is_keepalive()`. 4) In `_pool.py`/`_server.py`: drain the body on keep-alive and close streams on exit without propagating `KeyboardInterrupt` as an error. 5) Replicate identically in `ahttpx/*`. 6) Run `tests/test_parsers.py` (`test_parser_server`, `test_*_connection_close`).
- **Complexity**: High (7 files, two sync/async implementations, subtle states).
- **Blockers**: reproducing real keep-alive requires a live server/client; risk of breaking the client pool.

### rich_2725 — Box render order in tables (`rich/table.py`)
- **What it is**: the box `mid_*` elements appeared on the last line (footer) and the `foot_*` elements in the body.
- **What is missing**: swap the two segment blocks in `Table._render` so that mid stays in the body and foot at the close.
- **Strategy**: 1) Open `_render` and locate the list of tuples `(left, right, vertical)`. 2) Swap the mid/foot blocks. 3) Verify with the PS example (box with digits 1–9) and `test_placement_table_box_elements`, `test_section`.
- **Complexity**: Low. **Blockers**: none relevant; direct visual verification.

### rich_2943 — Clear hashed cache when clearing meta (`rich/style.py`)
- **What it is**: `Style.clear_meta_and_links` did not invalidate the cached hash → stale styles (origin of #2942).
- **What is missing**: reset the hash cache inside `clear_meta_and_links`.
- **Strategy**: 1) Read `Style` (cached `_hash`/`__hash__`). 2) Add hash cleanup in the method. 3) Run `test_clear_meta_and_links*`.
- **Complexity**: Low. **Blockers**: understanding the hash caching scheme.

### rich_3006 — Custom classes in repr (`rich/repr.py`, fixes #2875)
- **What it is**: `auto_rich_repr` failed with custom classes (automatic `__rich_repr__` decorator).
- **What is missing**: 1-line fix in `auto_rich_repr`.
- **Strategy**: 1) Reproduce with the issue's custom class. 2) Read `auto_rich_repr` and fix the handling of the case. 3) Run `tests/test_repr.py`.
- **Complexity**: Low. **Blockers**: none.

### rich_3043 — HTML export template (`rich/_export_format.py`)
- **What it is**: the `CONSOLE_HTML_FORMAT` template produced broken HTML (issue #3021).
- **What is missing**: 1-line fix in the template + pre-commit config adjustment (incidental).
- **Strategy**: 1) Export HTML from a test console and compare. 2) Fix the template. 3) Run `test_export_html*`, `test_save_html`.
- **Complexity**: Low. **Blockers**: none.

### rich_3052 — Prompt with case-insensitive choices (`rich/prompt.py`)
- **What it is**: new feature: `case_sensitive=True` parameter by default in `PromptBase.__init__` and `ask`.
- **What is missing**: plumb `case_sensitive` through the constructor + `ask` and compare normalizing case when it is `False`.
- **Strategy**: 1) Add the kwarg in `__init__` and every overload of `ask`. 2) In validation, compare `value.lower()` against lowercased choices if `case_sensitive=False`. 3) Run `test_prompt_str_case_insensitive`.
- **Complexity**: Medium (several signatures to keep consistent). **Blockers**: none; public API, keep the default `True` to avoid breaking compat.

### rich_3061 — `Text.extend_tabs` with styles (`rich/text.py`)
- **What it is**: `extend_tabs` replaced tabs with unstyled spaces, losing the spans over the tab.
- **What is missing**: new `Span.extend(cells)`, propagate the tab's style to the generated spaces, and change the `tab_size` default from `8` to `None` (delegating to `console.tab_size`) in `__init__`/`from_ansi`/`assemble`.
- **Strategy**: 1) Add `Span.extend`. 2) In the tab expansion path, extend the spans that cover the tab. 3) Change defaults `tab_size=8` → `None`. 4) Run `test_tabs_to_spaces_spans`, `test_extend_style` + the `test_text.py` suite.
- **Complexity**: Medium (spans/offsets interaction + default change with broad reach). **Blockers**: subtle regressions in any render with tabs.

### rich_3063 — Escape trailing backslash (`rich/markup.py`, fixes #2987)
- **What it is**: `escape` did not handle a backslash at the end of the string.
- **What is missing**: 3-line adjustment in `escape_backslashes`/`pop_style`.
- **Strategy**: 1) Reproduce `render("[foo]\\")`. 2) Fix the trailing backslash regex/branch. 3) Run `tests/test_markup.py`.
- **Complexity**: Low. **Blockers**: delicate regexes, test the edges (`\\`, `\\\\`).

### rich_3064 — Broken markdown table (`rich/markdown.py`, fixes #3053)
- **What it is**: markdown table rendering failed on certain input.
- **What is missing**: ~8-line fix in `Markdown.__rich_console__`.
- **Strategy**: 1) Reproduce with the issue's markdown. 2) Locate the table branch and fix it. 3) Run `test_markdown_table`, `test_partial_table`.
- **Complexity**: Low. **Blockers**: none.

### rich_3067 — Tilde in URLs (`rich/highlighter.py`, fixes #3057)
- **What it is**: the repr/URL highlighter did not accept `~` in URLs.
- **What is missing**: 1 line in the `ReprHighlighter` regex.
- **Strategy**: 1) Test URL highlighting with `~`. 2) Widen the character class. 3) Run `tests/test_highlighter.py`.
- **Complexity**: Low. **Blockers**: none.

### rich_3105 — Fix #3104 (`rich/_export_format.py`)
- **What it is**: minimal fix (1 line) in the HTML export CSS.
- **What is missing**: fix the template's `</style>` line.
- **Strategy**: 1) Export HTML and validate. 2) Apply the fix. 3) Run the export tests in `test_console.py`.
- **Complexity**: Low. **Blockers**: none.

### rich_3130 — Markdown tables with inline styles/links (`rich/markdown.py`)
- **What it is**: table cells with inline styles or links rendered incorrectly.
- **What is missing**: changes in `TableDataElement.create` to preserve inline styles inside cells.
- **Strategy**: 1) Reproduce a table with `[link]`/`[bold]` in cells. 2) Fix the creation of the cell element. 3) Run `test_inline_styles_in_table`, `test_inline_styles_with_justification`.
- **Complexity**: Medium (markdown→table→styles interaction). **Blockers**: combination of justification + styles.

### rich_3180 — Double-width characters disappear when wrapping (`rich/_wrap.py`, `rich/cells.py`)
- **What it is**: rewrite of `divide_line`/`words`: CJK characters (width 2) were lost or split when dividing lines.
- **What is missing**: rewrite the algorithm with cell offsets (`cell_offset`, `remaining_space`), correct fold with `chop_cells`, and adjustments in `set_cell_size`.
- **Strategy**: 1) Reproduce with CJK text + small width. 2) Rewrite `divide_line` measuring in cells, not chars. 3) Adjust `chop_cells`/`set_cell_size` in `cells.py`. 4) Run `test_cells.py` + `test_text.py` in full (includes `test_chop_cells_double_width_boundary`, `test_set_cell_size_infinite`).
- **Complexity**: High (wrapping algorithm, width invariants, many edges). **Blockers**: outputs depend on unicode width tables; easy regression.

### rich_3278 — Strip private escape sequences (`rich/ansi.py`)
- **What it is**: problematic private escape sequences reached the output.
- **What is missing**: 1 line in the `re_ansi` regex to filter them.
- **Strategy**: 1) Reproduce with the issue's sequence. 2) Widen the regex. 3) Run `test_strip_private_escape_sequences`, `test_decode_issue_2688`.
- **Complexity**: Low. **Blockers**: ANSI regex, risk of over-filtering.

### rich_3296 — Padding with background in Syntax (`rich/syntax.py`)
- **What it is**: the background override did not cover the padding.
- **What is missing**: include the padding in the style applied in `Syntax.__rich_console__`.
- **Strategy**: 1) Render `Syntax` with `background_color` + padding. 2) Extend the style to the padding. 3) Run `test_background_color_override_includes_padding`.
- **Complexity**: Low. **Blockers**: none.

### rich_3454 — `@` breaks highlighting in hyperlinks (`rich/highlighter.py`, #3327)
- **What it is**: the highlighting regex cut links with `@`.
- **What is missing**: 1 line in `ReprHighlighter`.
- **Strategy**: 1) Reproduce a link with `@`. 2) Adjust the regex. 3) Run `tests/test_highlighter.py`.
- **Complexity**: Low. **Blockers**: none.

### rich_3468 — Handle BrokenPipe (`rich/console.py`, fixes #1591)
- **What it is**: `BrokenPipeError` when piping output (e.g. `| head`) crashed.
- **What is missing**: catch `BrokenPipeError` in `render_lines`/`render_str`/`log`/`_check_buffer` (36 lines).
- **Strategy**: 1) Reproduce by closing the read pipe. 2) Wrap writes in try/except `BrokenPipeError` with silent exit. 3) Run `test_brokenpipeerror`.
- **Complexity**: Medium (several write points, clean-exit semantics). **Blockers**: reproducing a broken pipe in a test requires file mocks.

### rich_3469 — Superfluous space in markdown (fixes #3027)
- **What it is**: extra space in markdown render.
- **What is missing**: 1 line in `Markdown.__rich_console__`.
- **Strategy**: 1) Reproduce the issue's case. 2) Fix it. 3) Run `test_markdown_render`, `test_table_with_empty_cells`.
- **Complexity**: Low. **Blockers**: none.

### rich_3470 — Fix record and capture (`rich/console.py`, fixes #2563)
- **What it is**: `export_text` with `record=True` + `capture` failed.
- **What is missing**: 1 line in `_write_buffer`.
- **Strategy**: 1) Reproduce capture+record. 2) Fix flush/buffer. 3) Run `test_capture_and_record`, `test_brokenpipeerror`.
- **Complexity**: Low. **Blockers**: internal buffer state, subtle.

### rich_3471 — Exception in `append_tokens` (fixes #3014)
- **What it is**: `Text.append_tokens` raised an exception on certain input.
- **What is missing**: 1 guard line in `append_tokens`.
- **Strategy**: 1) Reproduce. 2) Add the guard. 3) Run `test_append_tokens`.
- **Complexity**: Low. **Blockers**: none.

### rich_3472 — Missing field in dataclass (`rich/pretty.py`, fixes #3417)
- **What it is**: `pretty` failed with a dataclass with a missing/atypical field.
- **What is missing**: 3 lines in `iter_attrs`.
- **Strategy**: 1) Reproduce the issue's dataclass. 2) Handle the absent field. 3) Run `test_dataclass_no_attribute`.
- **Complexity**: Low. **Blockers**: none.

### rich_3480 — Infinite loop in `append` (fixes #3479)
- **What it is**: `Text.append` entered an infinite loop appending to itself.
- **What is missing**: 2 lines in `append`/`append_text` (copy before extending).
- **Strategy**: 1) Reproduce `t.append(t)`. 2) Snapshot spans/text before mutating. 3) Run `test_append_loop_regression`.
- **Complexity**: Low. **Blockers**: aliasing of mutable objects.

### rich_3486 — Fine-grained error locations PEP 657 (`rich/traceback.py`, `rich/syntax.py`)
- **What it is**: bring Python 3.11's granular error ranges (PEP 657, `co_positions`) into traceback rendering.
- **What is missing**: `Frame.last_instruction`, `traceback.error_range`, `Syntax.stylize_range(..., style_before)` + `_SyntaxHighlightRange.style_before`, and underline the exact error range.
- **Strategy**: 1) Read `traceback.py::extract` and the offset calculation. 2) Extract `(lineno, end_lineno, col, end_col)` from the frame and store `last_instruction`. 3) Add `style_before` to `Syntax` and apply it with `stylize_before` so as not to cover existing highlighting. 4) Run `test_traceback_finely_grained*` on 3.11+ (on older versions the test is skipped).
- **Complexity**: High (depends on the Python version, bytecode offsets, syntax/traceback interaction). **Blockers**: only verifiable on 3.11+; `co_positions` absent on other versions.

### rich_3506 — Fix split cells (`rich/segment.py`, via textual#4996)
- **What it is**: `Segment._split_cells` split segments with wide characters incorrectly.
- **What is missing**: ~15 lines around `is_control`/split.
- **Strategy**: 1) Reproduce with emoji/CJK. 2) Fix the cell split. 3) Run `test_split_cells_*`.
- **Complexity**: Medium (cell arithmetic). **Blockers**: emoji vs double-width cases differ.
### rich_3518 — Highlight of columns added by `add_row` (`rich/table.py`)
- **What it is**: columns with `highlight=True` added via `add_row` were not highlighted.
- **What is missing**: 1 line in `Table`'s internal `add_cell` function.
- **Strategy**: 1) Create a table with a highlight column + `add_row`. 2) Propagate the style in `add_cell`. 3) Run `test_columns_highlight_added_by_add_row`.
- **Complexity**: Low. **Blockers**: none.

### rich_3521 — `Segment.split_cells` fix (`rich/segment.py`, via textual#5090)
- **What it is**: incorrect cell-based segment split on a certain edge.
- **What is missing**: partial rewrite of `_split_cells` (16 lines).
- **Strategy**: 1) Reproduce the textual#5090 case. 2) Fix the split arithmetic. 3) Run `test_split_cells_*`.
- **Complexity**: Medium (same family as 3506; width edges). **Blockers**: wide/emoji inputs.

### rich_3535 — Width fast-path regex (`rich/cells.py`, `rich/segment.py`)
- **What it is**: the regex that picks the fast-path for single-width strings failed → possible performance degradation and/or wrong measurement.
- **What is missing**: fix the regex + adjustment in `Segment.split_cells`.
- **Strategy**: 1) Identify strings that take the wrong path. 2) Fix the regex. 3) Run `test_is_single_cell_widths`, `test_chop_cells_mixed_width` + a quick benchmark if needed.
- **Complexity**: Medium (regex + performance). **Blockers**: measuring performance requires a microbenchmark, not just tests.

### rich_3675 — `TTY_COMPATIBLE` variable (`rich/console.py`, `rich/diagnose.py`)
- **What it is**: feature: `TTY_COMPATIBLE=1/0` forces or denies terminal mode (useful in CI where the output is not a tty but styles are still wanted).
- **What is missing**: read the env var in `Console.is_terminal` (taking precedence over `FORCE_COLOR`/isatty), harden the `NO_COLOR` check (`!= ""`), and report it in `diagnose.report`.
- **Strategy**: 1) Implement the order: explicit `force_terminal` → idlelib → Jupyter → `TTY_COMPATIBLE` → `FORCE_COLOR` → isatty. 2) Add it to `diagnose`. 3) Run `test_tty_compatible` + the console suite with an env-var matrix.
- **Complexity**: Medium (env-var precedence, many existing tests touch `is_terminal`). **Blockers**: tests sensitive to the environment's env vars (must isolate `environ`).

### rich_3676 — `Exception.__notes__` support (`rich/traceback.py`)
- **What it is**: feature: render `__notes__` (PEP 678) in tracebacks.
- **What is missing**: extract notes in `Traceback.extract` and render them (~12 lines + style).
- **Strategy**: 1) Raise an exception with `add_note`. 2) Propagate notes to `Stack`/`Trace` and render. 3) Run `test_notes`.
- **Complexity**: Medium (only 3.11+ has `__notes__`; needs a version guard). **Blockers**: the harness's Python version.

### rich_3718 — Panel title without background (`rich/panel.py`, fixes #3569)
- **What it is**: the `Panel` title lost the panel background (reverts the `7a38204` change).
- **What is missing**: 3 lines in `Panel.__rich_console__`/`align_text` to inherit the background style.
- **Strategy**: 1) Render a panel with a background `style` + title. 2) Apply the background to the title. 3) Run `test_title_text*` and the historical title-issue examples so as not to regress.
- **Complexity**: Medium (history of back-and-forth with title styles). **Blockers**: subtle visual regressions; it is worth testing several title/subtitle/border combos.

### rich_3772 — Recursion in tracebacks (`rich/traceback.py`, fixes #3708/#3682)
- **What it is**: recursive exceptions (cyclic `__cause__`/`__context__`, groups) hung or duplicated frames.
- **What is missing**: `_visited_exceptions` set in `extract`, skip exceptions already seen in groups, and do not follow `__cause__` when it is the same or already visited.
- **Strategy**: 1) Reproduce a self-caused exception and a group with duplicates. 2) Pass the visited set through `extract`'s recursion. 3) Run `test_recursive_exception`, `test_notes`.
- **Complexity**: Medium (recursion + groups + cause/context). **Blockers**: building the minimal repro is costly; risk of an infinite loop in the harness if it goes wrong (use a timeout).

### rich_3777 — `TTY_INTERACTIVE` variable (`rich/console.py`)
- **What it is**: feature complementary to TTY_COMPATIBLE: `TTY_INTERACTIVE=0` disables animations/progress/spinners in CI.
- **What is missing**: read the env var when initializing interactivity (~12 lines).
- **Strategy**: 1) Implement the env-var read. 2) Verify that progress/status do not animate with `TTY_INTERACTIVE=0`. 3) Run `test_tty_interactive`, `test_tty_compatible`.
- **Complexity**: Medium (same area as 3675; possible application order between the two). **Blockers**: if 3675 is solved first, this is almost trivial.

### rich_3782 — Padding in Syntax (`rich/syntax.py`, fixes #3727)
- **What it is**: the padding of `Syntax` blocks rendered incorrectly (background/measurements).
- **What is missing**: ~24 lines in `Syntax` (`__rich_console__`, number styles, `guess_lexer` incidental).
- **Strategy**: 1) Reproduce `Syntax` with padding. 2) Fix background application to the padding. 3) Run the `test_syntax.py` suite.
- **Complexity**: Medium (several methods touched). **Blockers**: interaction with themes/background override (see 3296).

### rich_3882 — Raw markup in prompt errors (`rich/prompt.py`)
- **What it is**: sometimes the validation error message showed unrendered markup.
- **What is missing**: 1 line in `on_validate_error` (render the error's markup).
- **Strategy**: 1) Reproduce a validation error with styles. 2) Render markup in the message. 3) Run `test_prompt_confirm_markup`.
- **Complexity**: Low. **Blockers**: the "sometimes" suggests a state race condition; the test guides.

### rich_3894 — Unusual `__qualname__` in inspect (`rich/_inspect.py`)
- **What it is**: `Inspect` broke with objects whose `__qualname__` is strange (e.g. slots).
- **What is missing**: 4-line guard in `_get_signature`.
- **Strategy**: 1) Reproduce with the test's object. 2) Add the guard. 3) Run `test_qualname_in_slots`.
- **Complexity**: Low. **Blockers**: none.

### rich_3905 — Blank line with progress disabled (`rich/progress.py`)
- **What it is**: with progress disabled a spurious blank line was emitted.
- **What is missing**: 4 lines in `Progress.start`.
- **Strategy**: 1) Reproduce disabled progress capturing stdout. 2) Avoid the line break. 3) Run `test_no_output_if_progress_is_disabled*`.
- **Complexity**: Low. **Blockers**: none.

### rich_3930 — Grapheme support (`rich/cells.py` + `rich/_unicode_data/*`)
- **What it is**: Rich never handled multi-codepoint emoji; this PR adopts generated unicode width tables (`tools/make_width_tables.py`, versions 4.1→17.0) and rewrites measurement by graphemes. It is the largest change in the segment: +12170/−544.
- **What is missing**: new `rich/_unicode_data/` package with per-version tables, `unicode_version` configurable in `get_character_cell_size`/`cell_len`, and migration of `CELL_WIDTHS` to the new tables.
- **Strategy**: 1) Do NOT rewrite by hand: understand that the tables are generated; the work is the wiring (`cells.py`: `get_character_cell_size(character, unicode_version)`, `_cell_len`, `split_graphemes`). 2) Keep a compatible default (`auto`). 3) Run `test_cells.py`, `test_unicode_data.py` (`test_load*`), `test_text.py` in full. 4) Verify performance (large tables at import).
- **Complexity**: High (volume, generated data, regression risk in every render). **Blockers**: diff size (agent context); dependence on the terminal's unicode version for visual validation; import-time.

### rich_3934 — Empty Live (`rich/live.py`, `rich/live_render.py`, fixes #3796)
- **What it is**: `Live` with empty content failed.
- **What is missing**: guard in `Live.stop` + type adjustment in `LiveRender.__init__`.
- **Strategy**: 1) Reproduce `Live` without a renderable. 2) Add guards. 3) Run `test_live_empty`, `test_live_screen`.
- **Complexity**: Medium (Live's start/stop/render lifecycle). **Blockers**: Live tests use refresh threads; flakiness possible.

### rich_3935 — Padding width in tables (`rich/table.py`, fixes #3871)
- **What it is**: padding incorrectly altered the column width calculation.
- **What is missing**: ~13 lines among `get_padding`, `_measure_column`, `_calculate_column_widths`.
- **Strategy**: 1) Reproduce a table with asymmetric padding. 2) Fix measurement to include padding. 3) Run `test_padding_width`, the `test_table.py`/`test_columns.py` suite.
- **Complexity**: Medium (column layout). **Blockers**: table golden outputs are fragile.

### rich_3938 — Background with soft wrap (`rich/console.py`, `rich/segment.py`, fixes #3838)
- **What it is**: `print`'s `style=` did not cover soft-wrapped lines (the style was applied per renderable and internal `\n` cut it).
- **What is missing**: new `Segment.split_lines_terminator` (yields `(line, had_newline)`) and rewrite of the styled branch in `Console.print` to apply style per line.
- **Strategy**: 1) Reproduce `console.print(texto_con_newlines, style=...)`. 2) Add `split_lines_terminator` to `Segment`. 3) Use it in `print`'s styled branch. 4) Run `test_soft_wrap*`, `test_split_lines*`.
- **Complexity**: Medium (new public Segment method + change in `print`, hot path). **Blockers**: `print` is the most used path; broad regression if the split fails.
### rich_3942 — Updated markdown styles (`rich/markdown.py`, `rich/default_styles.py`)
- **What it is**: Markdown restyling (blockquote, headers, etc.).
- **What is missing**: ~43 lines: changes in `default_styles.py`, `Markdown.__init__`/`__rich_console__`, element init.
- **Strategy**: 1) Compare render before/after with `_card_render`. 2) Apply new styles/structure. 3) Run `test_markdown.py` + `test_markdown_no_hyperlinks.py` (goldens will change: update deliberately, not blindly).
- **Complexity**: Medium (many goldens affected). **Blockers**: telling an intentional change from a regression in each golden.

### rich_3944 — Fix fonts (`rich/cells.py`, fixes #3943)
- **What it is**: targeted fix in `get_character_cell_size` (1 line, `unicode_version` parameter).
- **What is missing**: width lookup adjustment for a certain font/range.
- **Strategy**: 1) Reproduce the issue's char. 2) Fix it. 3) Run `test_nerd_font`, `test_split_graphemes`.
- **Complexity**: Low. **Blockers**: depends on 3930 (new tables); solve after 3930.

### rich_3953 — Fix ZWJ and edge cases (`rich/cells.py`, fixes #3947/#3950)
- **What it is**: ZWJ sequences (composite emoji 👨‍👩‍👧) and edge cases measured with the wrong width.
- **What is missing**: ~16 lines in `get_character_cell_size`/`_cell_len`.
- **Strategy**: 1) Reproduce with the issue's ZWJ. 2) Fix measurement. 3) Run `test_zwj`, `test_non_printable`, `test_nerd_font`.
- **Complexity**: Medium (depends on 3930; subtle ZWJ semantics). **Blockers**: same as 3944 + variability by unicode version.

### rich_4006 — Infinite loop in `split_graphemes` (fixes #3958)
- **What it is**: `split_graphemes` did not advance on certain input → infinite loop.
- **What is missing**: ~33 lines in `_cell_len`/`split_graphemes` (guarantee cursor progress).
- **Strategy**: 1) Reproduce with a timeout (the repro hangs). 2) Ensure a minimum advance per iteration. 3) Run `test_split_graphemes`, `test_chop_cells_zero_width`.
- **Complexity**: Medium (graphemes family; the repro hangs the harness without a timeout). **Blockers**: always run the repro with `timeout`.

### rich_4070 — Perf: defer imports in Console/RichHandler (`rich/console.py` and 8 other modules)
- **What it is**: `from rich.console import Console` took 78ms; the PR defers imports used only in certain paths (1.5x–1.75x faster).
- **What is missing**: move module imports to function imports in `console.py`, `logging.py`, `syntax.py`, `segment.py`, `emoji.py`, `theme.py`, `protocol.py`, `repr.py`, `_emoji_replace.py` (~71+/57-), plus a local `is_expandable` in `_collect_renderables`.
- **Strategy**: 1) Measure baseline with `time python -c "from rich.console import Console"`. 2) Move imports to the usage paths; beware of annotation-only imports (use `TYPE_CHECKING`). 3) Re-measure (target ~52ms/57ms). 4) Run a broad suite: deferring imports breaks third-party `from X import Y` and definition-time references.
- **Complexity**: High (9 files, deferred `NameError` risk, benefit only measurable with a benchmark). **Blockers**: verify that no moved symbol is used at module level; the PR's test is about perf, not functional.

### rich_4075 — Empty `print` with `end` + drop Python 3.8 (`rich/console.py`, fixes #3740)
- **What it is**: `console.print(end=...)` with no content failed; 3.8 support is also dropped.
- **What is missing**: ~12 lines in `Console.print`/`export_text` (handle an empty renderable with `end`).
- **Strategy**: 1) Reproduce empty `print(end="x")`. 2) Fix the empty branch. 3) Run `test_print_empty_with_end`, `test_print*`.
- **Complexity**: Low. **Blockers**: none.

### rich_4076 — Preserve newlines in ANSI decode (`rich/ansi.py`, fixes #3577)
- **What it is**: `AnsiDecoder.decode` lost newlines.
- **What is missing**: 3 lines in `decode`.
- **Strategy**: 1) Reproduce with ANSI containing `\n`. 2) Emit a line segment in the split. 3) Run `test_decode_newlines`, `test_ansi.py` suite.
- **Complexity**: Low. **Blockers**: none.

### rich_4077 — Proxy `isatty` (`rich/file_proxy.py`, fixes #4041)
- **What it is**: `FileProxy.flush` (and proxy) did not delegate `isatty` → broken terminal detection under proxy.
- **What is missing**: 3 lines (delegate `isatty` to the wrapped file).
- **Strategy**: 1) Reproduce a proxy without isatty. 2) Add delegation. 3) Run `test_isatty`, `test_new_lines`.
- **Complexity**: Low. **Blockers**: none.

### rich_4079 — Inline code in table cells (`rich/markdown.py`, fixes #4038)
- **What it is**: inline code (backticks) inside markdown table cells rendered incorrectly.
- **What is missing**: 4 lines in the cell element/justification init.
- **Strategy**: 1) Reproduce a table with `código` in cells. 2) Fix it. 3) Run `test_inline_code_in_table_cells`, `test_table_with_empty_cells`.
- **Complexity**: Low. **Blockers**: none.

## Aggregated table

### Complexity distribution

| Complexity | Count | Tasks |
|---|---|---|
| High | 5 | httpx_3672, rich_3180, rich_3486, rich_3930, rich_4070 |
| Medium | 19 | rich_3052, rich_3061, rich_3130, rich_3468, rich_3506, rich_3521, rich_3535, rich_3675, rich_3676, rich_3718, rich_3772, rich_3777, rich_3782, rich_3934, rich_3935, rich_3938, rich_3942, rich_3953, rich_4006 |
| Low | 25 | rich_2725, rich_2943, rich_3006, rich_3043, rich_3063, rich_3064, rich_3067, rich_3105, rich_3278, rich_3296, rich_3454, rich_3469, rich_3470, rich_3471, rich_3472, rich_3480, rich_3518, rich_3882, rich_3894, rich_3905, rich_3944, rich_4075, rich_4076, rich_4077, rich_4079 |
| **Total** | **49** | |

### Top 5 blockers of the segment

1. **Fragile render goldens** — tables, markdown, syntax and panel compare exact strings; any layout fix (3935, 3942, 3718, 2725, 3518) requires telling an intentional change from a regression.
2. **Unicode widths / Python version** — graphemes, ZWJ, CJK and PEP 657/`__notes__` depend on the harness's unicode and Python (3.11+) versions (3180, 3930, 3944, 3953, 4006, 3486, 3676).
3. **Environment-sensitive tests** — `is_terminal`, env vars (`TTY_COMPATIBLE`, `TTY_INTERACTIVE`, `NO_COLOR`) and `Live` threads are flaky depending on the runner (3675, 3777, 3934).
4. **Repros that hang or need live infra** — infinite loops (3480, 4006, 3772) require `timeout`; httpx keep-alive requires a real server (httpx_3672).
5. **Hot paths with broad regression** — `Console.print`, `Segment`, `Text.append`, deferred imports: the new test passes but something else breaks (3938, 3480, 4070, 3180). They require running the whole module suite, not just the task's test.
