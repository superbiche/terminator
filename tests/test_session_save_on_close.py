#!/usr/bin/env python
# Terminator by Chris Jones <cmsj@tenshu.net>
# GPL v2 only
"""test_session_save_on_close.py - tests for the save-session-on-window-close
option: startup layout selection, session snapshot writing, and the
window-close dialog response handling."""

import argparse

# util first: it pins the Gtk 3.0 namespace, which terminator.py imports
# without an explicit require_version (upstream import-order dependency).
from terminatorlib.util import SAVED_SESSION_LAYOUT  # noqa: I001
from terminatorlib import optionparse
from terminatorlib import window as window_mod
from terminatorlib.window import Window


class FakeConfig(object):
    def __init__(self, restore=False, layouts=(), prompt_save=True,
                 replace_ok=True):
        self.items = {'restore_session': restore,
                      'prompt_save_on_close': prompt_save}
        self.layouts = list(layouts)
        self.replace_ok = replace_ok
        self.replaced = None
        self.added = None
        self.saved = 0

    def __getitem__(self, key):
        return self.items[key]

    def __setitem__(self, key, value):
        self.items[key] = value

    def list_layouts(self):
        return list(self.layouts)

    def replace_layout(self, name, layout):
        self.replaced = (name, layout)
        return self.replace_ok

    def add_layout(self, name, layout):
        self.added = (name, layout)

    def save(self):
        self.saved += 1


class FakeTerminator(object):
    def __init__(self, layout):
        self.layout = layout
        self.save_cwd_seen = None

    def describe_layout(self, save_cwd=False):
        self.save_cwd_seen = save_cwd
        return self.layout


class FakeWindow(object):
    def __init__(self, config, layout=None, response=None):
        self.config = config
        self.terminator = FakeTerminator(layout if layout is not None
                                         else {'terminal0': {'type': 'Terminal'}})
        self.response = response
        self.save_calls = 0

    def get_child(self):
        return object()

    def construct_confirm_close(self, window, child, save_on_close=False):
        self.save_on_close_seen = save_on_close
        return self.response

    def save_session_layout(self):
        self.save_calls += 1
        return Window.save_session_layout(self)


class TestSelectStartupLayout(object):
    def options(self, layout=None, select=False):
        return argparse.Namespace(layout=layout, select=select)

    def test_plain_launch_restores_saved_session(self):
        cfg = FakeConfig(restore=True, layouts=[SAVED_SESSION_LAYOUT])
        chosen = optionparse.select_startup_layout(
            self.options(), cfg, explicit_layout=False)
        assert chosen == SAVED_SESSION_LAYOUT

    def test_explicit_layout_flag_wins(self):
        cfg = FakeConfig(restore=True, layouts=[SAVED_SESSION_LAYOUT])
        chosen = optionparse.select_startup_layout(
            self.options(layout='mylayout'), cfg, explicit_layout=True)
        assert chosen == 'mylayout'

    def test_select_dialog_wins(self):
        cfg = FakeConfig(restore=True, layouts=[SAVED_SESSION_LAYOUT])
        chosen = optionparse.select_startup_layout(
            self.options(layout='default', select=True), cfg,
            explicit_layout=False)
        assert chosen == 'default'

    def test_no_saved_layout_falls_back(self):
        cfg = FakeConfig(restore=True, layouts=[])
        chosen = optionparse.select_startup_layout(
            self.options(layout='default'), cfg, explicit_layout=False)
        assert chosen == 'default'

    def test_flag_off_stays_default(self):
        cfg = FakeConfig(restore=False, layouts=[SAVED_SESSION_LAYOUT])
        chosen = optionparse.select_startup_layout(
            self.options(layout='default'), cfg, explicit_layout=False)
        assert chosen == 'default'


class TestSaveSessionLayout(object):
    def test_snapshot_replaces_existing_layout(self):
        layout = {'window0': {'type': 'Window'},
                  'terminal0': {'type': 'Terminal', 'directory': '/tmp'}}
        cfg = FakeConfig(layouts=[SAVED_SESSION_LAYOUT])
        win = FakeWindow(cfg, layout=layout)
        assert win.save_session_layout() is True
        assert cfg.replaced == (SAVED_SESSION_LAYOUT, layout)
        assert cfg.added is None
        assert cfg.items['restore_session'] is True
        assert cfg.saved == 1
        assert win.terminator.save_cwd_seen is True

    def test_snapshot_adds_when_no_existing_layout(self):
        cfg = FakeConfig(replace_ok=False)
        win = FakeWindow(cfg)
        assert win.save_session_layout() is True
        assert cfg.replaced is not None
        assert cfg.added == (SAVED_SESSION_LAYOUT,
                             {'terminal0': {'type': 'Terminal'}})
        assert cfg.items['restore_session'] is True

    def test_empty_layout_saves_nothing(self):
        cfg = FakeConfig()
        win = FakeWindow(cfg, layout={})
        assert win.save_session_layout() is False
        assert cfg.replaced is None
        assert cfg.added is None
        assert cfg.saved == 0


class TestOnDeleteEventResponses(object):
    class Maker(object):
        def isinstance(self, widget, kind):
            return True

    def setup_method(self, method):
        self.saved_factory = window_mod.Factory
        window_mod.Factory = lambda: TestOnDeleteEventResponses.Maker()

    def teardown_method(self, method):
        window_mod.Factory = self.saved_factory

    def invoke(self, win):
        return Window.on_delete_event(win, None, None)

    def test_save_response_saves_and_closes(self):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        cfg = FakeConfig(restore=False, layouts=[])
        win = FakeWindow(cfg, response=Gtk.ResponseType.OK)
        assert self.invoke(win) is False  # window closes
        assert win.save_calls == 1
        assert cfg.items['restore_session'] is True

    def test_plain_close_discards_saved_session(self):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        cfg = FakeConfig(restore=True, layouts=[SAVED_SESSION_LAYOUT])
        win = FakeWindow(cfg, response=Gtk.ResponseType.ACCEPT)
        assert self.invoke(win) is False  # window closes
        assert win.save_calls == 0
        assert cfg.items['restore_session'] is False
        assert cfg.saved == 1

    def test_cancel_keeps_window_and_flag(self):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        cfg = FakeConfig(restore=True, layouts=[SAVED_SESSION_LAYOUT])
        win = FakeWindow(cfg, response=Gtk.ResponseType.REJECT)
        assert self.invoke(win) is True  # window stays
        assert win.save_calls == 0
        assert cfg.items['restore_session'] is True
        assert cfg.saved == 0

    def test_save_option_off_does_not_offer_save(self):
        cfg = FakeConfig(prompt_save=False)
        win = FakeWindow(cfg, response=None)
        Window.on_delete_event(win, None, None)
        assert win.save_on_close_seen is False
