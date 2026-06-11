# Progress

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
