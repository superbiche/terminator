# Progress

## 2026-06-29 GTK notebook detachable-tab crash mitigation

### Current branch state

- Working branch: `superbiche/local-detachable-tabs-fix`
- Base branch: `superbiche/daily-stable`
- Goal: keep detachable tabs usable while avoiding the GTK 3.24.52 crash seen after an aborted native detachable-tab drag.

### Crash finding

- Terminator crashed on 2026-06-29 at 09:50:28 CEST.
- Command in coredump:
  - `/usr/bin/python3 /home/michel/.local/bin/terminator --toggle-visibility`
- Signal:
  - `SIGSEGV`
- GTK stack resolved with debuginfo:
  - `gtk_notebook_drag_end()` at `gtknotebook.c:3743`
  - crashing line dereferenced `priv->dnd_window` after GTK had already reached a drag-abort timeout path.
- Relevant private GTK state at crash:
  - `priv->dnd_window = 0x0`
  - `priv->detached_tab` was non-null
  - `priv->operation = DRAG_OPERATION_NONE`
- The user was not actively dragging at the exact crash moment, but had dragged tabs shortly before; this matches GTK's delayed drag-abort timeout path.

### Local fix

- `terminatorlib/notebook.py` now keeps GTK tab reordering enabled but disables GTK's native detachable-tab DND state per page:
  - `set_tab_detachable(page, False)`
  - `set_tab_reorderable(page, True)`
- Terminator implements detach-to-new-window itself by tracking tab-label button press, motion, and release events.
- The current user-facing tradeoff:
  - left/right tab movement works
  - dragging tiles inside a tab is more stable and no longer flickers as much
  - dragging a tab top/down can eagerly detach it into a new window
  - the detached window's tile can still be moved back into another tab, so this is acceptable as a local daily-driver fix

### Upstream options

1. Detach only once the pointer leaves the whole Terminator window or notebook area, rather than leaving the tab header band.
2. Prefer this if upstreaming: enter a custom detach-intent mode on cross-axis tab drag, but create the new window only on button release outside the source notebook/window. Releasing back inside should cancel cleanly. This best matches GTK's native feel while avoiding GTK's native detachable-tab DND crash path.
3. Preserve GTK native reorder exactly while replacing only the native detach path. This is ideal behaviorally, but may be harder to prove safe because GTK private notebook drag state is not available from PyGObject.

### Verification and artifacts

- Worker handoff:
  - `/tmp/codex-judge-handoffs/2026-06-29-100624-terminator-codex.md`
- External review artifact:
  - `/var/tmp/terminator-sibling-fix-external-review-2026-06-29.md`
- Review verdict:
  - no blocking findings for local use
  - residual upstream risk is the eager top/down detach behavior documented above
- User installed and tested the patch locally on 2026-06-29.

## 2026-06-11 Terminator crash investigation and fork strategy

### Current branch state

- Working branch: `superbiche/daily-stable`
- Base: current upstream `origin/master` at `d7044357`
- Local fix commit: `275a13f7 Avoid recursive paned allocation updates`
- Remote `origin` points to upstream `https://github.com/gnome-terminator/terminator`
- `gh repo view` reported read-only permission on upstream, so nothing was pushed.
- Worktree still has Michel's pre-existing unstaged `.gitignore` change:
  - `.gitignore` currently ignores `*`
  - This was preserved and not committed.

### Crash finding

- Terminator crashed on 2026-06-10 around 12:02 CEST.
- Command in coredump:
  - `/usr/bin/python3 /home/michel/.local/bin/terminator --toggle-visibility`
- Signal:
  - `SIGSEGV`
- Stack pointed into PyGObject marshalling during GTK allocation:
  - `_gi.cpython-314...so`
  - `pygi_argument_to_py`
  - `pygi_signal_closure_marshal`
  - GTK size allocation path involving `GtkWindow`, `GtkNotebook`, and `GtkPaned`
- Environment observed:
  - Python 3.14.5
  - GTK 3.24.52
  - PyGObject 3.56.3
  - VTE 0.84.0
  - Wayland

### Local fix

Changed `terminatorlib/paned.py::Paned.new_size`.

Previous behavior:

```python
self.set_position(self.get_position())
```

This re-applied the current `GtkPaned` position during every normal child `size-allocate`, which may re-enter GTK allocation while PyGObject is marshalling the signal.

New behavior:

```python
newratio = self.ratio_by_position(
    self.get_length(),
    self.get_handlesize(),
    self.get_position()
)
if newratio is not None:
    self.ratio = newratio
```

This preserves the ratio bookkeeping without forcing another `GtkPaned.set_position()` during normal allocation.

### Verification so far

Passed:

- `git diff --check`
- `python3 -m compileall -q terminatorlib`
- `python3 -m doctest -v tests/test_signalman.py tests/test_borg.py`
  - 28 doctests passed
- `python3 -m pytest tests/test_borg.py tests/test_signalman.py`
  - 2 passed

Full suite on current upstream base:

- Command: `python3 -m pytest tests`
- Result: 17 passed, 4 failed
- Remaining failures are in `tests/test_prefseditor_keybindings.py`.
- These failures appear unrelated to the paned crash path and are GTK/GDK accelerator normalization expectations on this local Python 3.14/GTK environment.

### Upstream signal

- Local `master` was 86 commits behind upstream before rebasing.
- Upstream `origin/master` includes recent Python 3.14 test work:
  - `c5e50d4d Merge pull request #1092`
  - `22785efe tests: fix accelerator_parse hash mismatch on Python 3.14`
- Upstream still has the old `self.set_position(self.get_position())` call in `terminatorlib/paned.py`.
- Searches did not find an existing upstream issue/PR matching this `GtkPaned`/`size-allocate`/PyGObject segfault path.

### Contribution strategy signal

- Recommended posture: keep `superbiche/daily-stable` as a soft fork branch, rebase regularly on upstream, and upstream small focused fixes only when the effort is low.
- Do not hard-fork yet.
- This paned crash mitigation is a reasonable candidate for a small upstream PR.
- If submitted, include:
  - coredump summary, without private host details
  - the `--toggle-visibility` crash context
  - PyGObject/GTK stack pointing at `size-allocate`
  - explanation that the change avoids re-calling `set_position()` from normal allocation
  - test results, with the unrelated keybinding failures noted separately

### AI policy signal

- No explicit no-AI-code policy found in repository files or GitHub templates.
- A maintainer comment on PR discussion indicated no objection to LLM-authored commits per se, especially small one-line fixes.
- At least one automated/AI-assisted contribution was merged upstream.

### Suggested next session

1. Decide whether to push `superbiche/daily-stable` to Michel's fork remote.
2. Optionally add a fork remote if absent.
3. Re-run targeted smoke checks after using the branch in daily Terminator sessions.
4. If stable, open a focused upstream PR for `terminatorlib/paned.py`.
5. Separately investigate the remaining Python 3.14/GTK keybinding test failures if they matter for upstream CI or local confidence.
