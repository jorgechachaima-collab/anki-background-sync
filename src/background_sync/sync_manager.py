"""The scheduler that decides when to sync and runs the sync quietly.

How a cycle works
-----------------
1. A timer ticks every few seconds on the main thread.
2. When a sync is due (interval elapsed) and Anki is idle (no keyboard,
   mouse or touch input for ``idle_seconds``, no dialog or progress window
   open, no answer side showing in the reviewer), we ask the backend for the
   sync status. This is cheap: local changes are detected without network,
   and the AnkiWeb check does not lock the collection.
3. If nothing changed on either side, we only record the check.
4. Otherwise we run Anki's own normal sync (``col.sync_collection``) on the
   collection thread, without a progress window. The steps afterwards mirror
   ``aqt.sync.sync_collection`` and ``AnkiQt._sync_collection_and_media``.
   The backend holds the collection lock during the sync, so if the user
   comes back and touches Anki meanwhile, we abort the sync (it rolls back)
   and retry at the next idle moment instead of freezing the window.
5. If AnkiWeb asks for a full sync, we hand over to Anki's own
   ``aqt.sync.full_sync`` dialog, which asks the user what to do. If the
   user cancels, we stop asking until they sync manually.
"""

from __future__ import annotations

import logging
import math
import sys
import time
from concurrent.futures import Future
from typing import Callable

import aqt
from anki.errors import Interrupted, NetworkError, SyncError, SyncErrorKind
from aqt import gui_hooks
from aqt.qt import QApplication, QEvent, QMessageBox, QObject, QTimer, qconnect
from aqt.utils import showText, tooltip

from . import config as config_mod
from .i18n import t


def _make_logger() -> logging.Logger:
    """Anki >= 24.06 gives add-ons their own log file. On older versions,
    anything written to stderr pops up Anki's error window, so log to stdout."""
    try:
        manager = aqt.mw.addonManager
        if hasattr(manager, "get_logger"):
            return manager.get_logger(__name__)
    except Exception:
        pass
    logger = logging.getLogger("background_sync")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.propagate = False
    return logger


log = _make_logger()

TICK_MS = 5_000
# If the reviewer is showing an answer, wait for the next card unless the
# user has walked away for this long.
ANSWER_SIDE_GRACE_S = 10 * 60
# Retry delays after failures: 1, 2, 4… minutes, capped by the interval.
FIRST_RETRY_S = 60
# Network errors are common right after waking from sleep: only tell the
# user once several attempts in a row have failed.
NETWORK_NOTICE_AFTER = 3
# Other errors (server message, database check required, client too old…)
# will not fix themselves: stop retrying after this many, until a manual sync.
STOP_AFTER_FAILURES = 3
# Ticks without any visible dialog before we decide that a full-sync prompt,
# or a sync started by Anki itself, ended without telling us.
WATCHDOG_TICKS = 3
INTERACTIVE_STATES = ("deckBrowser", "overview", "review")


def _event_types() -> frozenset:
    names = ("KeyPress", "MouseButtonPress", "Wheel", "TouchBegin", "TabletPress")
    found = []
    for name in names:
        value = getattr(QEvent.Type, name, None)
        if value is not None:
            found.append(value)
    return frozenset(found)


_INPUT_EVENTS = _event_types()


class _ActivityFilter(QObject):
    """Records the time of the last keyboard/mouse/touch input in Anki."""

    def __init__(self, on_activity: Callable[[], None]) -> None:
        super().__init__()
        self._on_activity = on_activity

    def eventFilter(self, obj, event):  # noqa: N802 (Qt API)
        try:
            if event.type() in _INPUT_EVENTS:
                self._on_activity()
        except Exception:
            pass
        return False


class BackgroundSync:
    def __init__(self, mw: aqt.main.AnkiQt) -> None:
        self.mw = mw
        self.conf = config_mod.load()
        self.on_change: Callable[[], None] = lambda: None
        self.indicator = None  # set by __init__.py

        # "idle" | "checking" | "syncing" | "full_sync"
        self.state = "idle"
        self.session_start = time.time()
        self.last_sync: float | None = None  # last confirmed successful sync
        self.last_check: float | None = None  # last "nothing to do" check
        self.last_attempt: float | None = None
        self.last_error: str | None = None
        self.failures = 0
        self.stopped_on_error = False
        self.need_login = False
        self.full_sync_pending = False
        self.paused_until: float | None = None
        self.waiting_for_idle = False

        self._last_activity = time.monotonic()
        self._closing = False
        self._generation = 0
        self._manual = False
        self._will_start_fired = False
        self._firing_own_hooks = False
        self._external_sync_running = False
        self._watchdog = 0
        self._timer: QTimer | None = None
        self._filter: _ActivityFilter | None = None

    # ------------------------------------------------------------------
    # Setup

    def install(self) -> None:
        self._filter = _ActivityFilter(self._note_activity)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self._filter)

        self._timer = QTimer(self.mw)
        qconnect(self._timer.timeout, self._tick)
        self._timer.start(TICK_MS)

        gui_hooks.profile_did_open.append(self._on_profile_open)
        gui_hooks.profile_will_close.append(self._on_profile_close)
        gui_hooks.sync_will_start.append(self._on_any_sync_start)
        gui_hooks.sync_did_finish.append(self._on_any_sync_finish)
        # Reviewer activity also counts (e.g. answers coming from other tools).
        gui_hooks.reviewer_did_show_question.append(self._on_reviewer_activity)
        gui_hooks.reviewer_did_show_answer.append(self._on_reviewer_activity)

    def reload_config(self) -> None:
        self.conf = config_mod.load()
        self._changed()

    # ------------------------------------------------------------------
    # Public actions (menu)

    def sync_now(self) -> None:
        """Manual request from the indicator menu."""
        mw = self.mw
        if self.state != "idle":
            return
        self.stopped_on_error = False
        if self.need_login or self.full_sync_pending or not self._auth():
            # Anki's own button handles the login form and the full-sync dialog.
            self.full_sync_pending = False
            self.need_login = False
            mw.on_sync_button_clicked()
            return
        if self._basic_blocker() is not None:
            tooltip(t("tooltip_busy"), parent=mw)
            return
        self._start_sync(manual=True)

    def pause_for(self, seconds: int) -> None:
        self.paused_until = time.time() + seconds
        self._changed()

    def pause_for_session(self) -> None:
        self.paused_until = math.inf
        self._changed()

    def resume(self) -> None:
        self.paused_until = None
        self._changed()

    def is_paused(self) -> bool:
        if self.paused_until is None:
            return False
        if time.time() >= self.paused_until:
            self.paused_until = None
            return False
        return True

    def seconds_until_due(self) -> float:
        return max(0.0, self._next_due() - time.time())

    def last_ok_time(self) -> float | None:
        times = [x for x in (self.last_sync, self.last_check) if x is not None]
        return max(times) if times else None

    # ------------------------------------------------------------------
    # Activity and hooks

    def _note_activity(self) -> None:
        self._last_activity = time.monotonic()
        if self.state == "syncing" and not self._manual:
            # The user is back: free the collection right away rather than
            # making the window wait for the sync to finish.
            self._abort_sync()

    def _on_reviewer_activity(self, *_args) -> None:
        self._last_activity = time.monotonic()

    def _idle_seconds(self) -> float:
        return time.monotonic() - self._last_activity

    def _abort_sync(self) -> None:
        try:
            self.mw.col.abort_sync()
        except Exception:
            pass

    def _on_profile_open(self) -> None:
        self._generation += 1
        self._closing = False
        self._external_sync_running = False
        self._watchdog = 0
        self.state = "idle"
        self.session_start = time.time()
        self.last_sync = None
        self.last_check = None
        self.last_attempt = None
        self.last_error = None
        self.failures = 0
        self.stopped_on_error = False
        self.need_login = False
        self.full_sync_pending = False
        self._changed()

    def _on_profile_close(self) -> None:
        self._generation += 1
        self._closing = True
        if self.state == "syncing":
            self._abort_sync()

    def _on_any_sync_start(self) -> None:
        if self._firing_own_hooks:
            return
        self._external_sync_running = True
        self._watchdog = 0

    def _on_any_sync_finish(self) -> None:
        if self._firing_own_hooks:
            return
        # A sync started by Anki itself (button, startup, shutdown). It may
        # have failed or been cancelled, so ask the backend what the state is.
        self._external_sync_running = False
        self.last_attempt = time.time()
        self.failures = 0
        self.last_error = None
        self.stopped_on_error = False
        self.full_sync_pending = False
        try:
            self.need_login = not bool(self.mw.pm.sync_auth())
        except Exception:
            pass
        if not self._closing:
            self._verify_status()
        self._changed()

    # ------------------------------------------------------------------
    # Scheduling

    def _auth(self):
        try:
            return self.mw.pm.sync_auth()
        except Exception:
            return None

    def _next_due(self) -> float:
        interval = self.conf.interval_minutes * 60
        if self.failures and self.last_attempt is not None:
            delay = min(interval, FIRST_RETRY_S * 2 ** (self.failures - 1))
            return self.last_attempt + delay
        base = self.last_ok_time() or self.session_start
        if self.last_attempt is not None:
            base = max(base, self.last_attempt)
        return base + interval

    def _open_editing_window(self) -> bool:
        """True if a window with unsaved user input is open."""
        try:
            dialogs = aqt.dialogs._dialogs
        except Exception:
            return False
        for name in ("FilteredDeckConfigDialog",):
            entry = dialogs.get(name)
            if entry and entry[1] is not None:
                return True
        return False

    def _basic_blocker(self) -> str | None:
        """Reasons that prevent any sync right now, even a manual one."""
        mw = self.mw
        if self._closing or getattr(mw, "col", None) is None:
            return "no collection"
        if getattr(mw, "state", None) not in INTERACTIVE_STATES:
            return "state"
        if getattr(mw, "safeMode", False) or getattr(mw, "restoring_backup", False):
            return "safe mode"
        if self._external_sync_running:
            return "anki sync"
        try:
            if mw.progress.busy():
                return "progress window"
        except Exception:
            pass
        if QApplication.activeModalWidget() is not None:
            return "modal dialog"
        try:
            if mw.media_syncer.is_syncing():
                return "media sync"
        except Exception:
            pass
        if self._open_editing_window():
            return "editing window"
        return None

    def _idle_blocker(self) -> str | None:
        idle = self._idle_seconds()
        if idle < self.conf.idle_seconds:
            return "user active"
        mw = self.mw
        if mw.state == "review":
            reviewer_state = getattr(getattr(mw, "reviewer", None), "state", None)
            if reviewer_state == "answer" and idle < ANSWER_SIDE_GRACE_S:
                return "answer showing"
        return None

    def _tick(self) -> None:
        try:
            self._run_watchdog()
            self._maybe_start()
        except Exception:
            log.exception("background sync tick failed")
            self.state = "idle"
        self._changed()

    def _no_dialog_showing(self) -> bool:
        if QApplication.activeModalWidget() is not None:
            return False
        try:
            if self.mw.progress.busy():
                return False
        except Exception:
            pass
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible():
                return False
        return True

    def _run_watchdog(self) -> None:
        """Recover if a full-sync prompt (ours or Anki's) ended without a
        callback, e.g. the user refused to close an Add window."""
        stuck = self.state == "full_sync" or self._external_sync_running
        if not stuck or not self._no_dialog_showing():
            self._watchdog = 0
            return
        self._watchdog += 1
        if self._watchdog < WATCHDOG_TICKS:
            return
        self._watchdog = 0
        log.info("sync dialog closed without callback; resetting state")
        if self.state == "full_sync":
            self._after_full_sync(self._generation)
        else:
            self._external_sync_running = False
            self.last_attempt = time.time()
            self._verify_status()

    def _maybe_start(self) -> None:
        self.waiting_for_idle = False
        if self.state != "idle" or self._closing:
            return
        if not self.conf.enabled or self.is_paused() or self.stopped_on_error:
            return
        if not self._auth():
            self.need_login = True
            return
        self.need_login = False
        if time.time() < self._next_due():
            return
        if self._basic_blocker() is not None:
            return
        if self._idle_blocker() is not None:
            self.waiting_for_idle = True
            return
        self._check_status()

    # ------------------------------------------------------------------
    # Status check (cheap)

    def _check_status(self) -> None:
        mw = self.mw
        auth = self._auth()
        col = mw.col
        gen = self._generation
        self.state = "checking"
        self._changed()

        mw.taskman.run_in_background(
            lambda: col.sync_status(auth),
            lambda fut: self._on_status_done(fut, gen),
            uses_collection=False,
        )

    def _on_status_done(self, fut: Future, gen: int) -> None:
        if gen != self._generation:
            return
        self.state = "idle"
        if self._closing or self.mw.col is None:
            return
        try:
            out = fut.result()
        except Exception as err:
            self._record_error(err)
            self._changed()
            return

        if out.new_endpoint:
            self.mw.pm.set_current_sync_url(out.new_endpoint)
        try:
            self.mw.toolbar.set_sync_status(out)
        except Exception:
            pass

        if out.required == out.NO_CHANGES:
            self._record_check()
        elif out.required == out.FULL_SYNC and self.full_sync_pending:
            # The user already declined; do not ask again until a manual sync.
            self.last_attempt = time.time()
        elif self._basic_blocker() is None and self._idle_blocker() is None:
            self._start_sync()
        self._changed()

    def _verify_status(self) -> None:
        """After a sync we did not fully observe, ask the backend whether the
        collection is now in sync, and update the indicator accordingly."""
        mw = self.mw
        auth = self._auth()
        if mw.col is None or not auth:
            return
        col = mw.col
        gen = self._generation

        def on_done(fut: Future) -> None:
            if gen != self._generation or self.mw.col is None:
                return
            try:
                out = fut.result()
            except Exception:
                return
            if out.required == out.FULL_SYNC:
                self.full_sync_pending = True
            elif out.required == out.NO_CHANGES:
                self.last_sync = time.time()
                self.full_sync_pending = False
            self._changed()

        mw.taskman.run_in_background(
            lambda: col.sync_status(auth), on_done, uses_collection=False
        )

    # ------------------------------------------------------------------
    # Normal sync (mirrors aqt.sync.sync_collection, without progress window)

    def _start_sync(self, manual: bool = False) -> None:
        mw = self.mw
        auth = self._auth()
        col = mw.col
        gen = self._generation
        media = mw.pm.media_syncing_enabled()
        self.state = "syncing"
        self._manual = manual
        self.last_attempt = time.time()
        self._fire_own(gui_hooks.sync_will_start)
        self._will_start_fired = True
        try:
            mw.toolbar.set_sync_active(True)
        except Exception:
            pass
        self._changed()

        mw.taskman.run_in_background(
            lambda: col.sync_collection(auth, media),
            lambda fut: self._on_sync_done(fut, gen),
        )

    def _on_sync_done(self, fut: Future, gen: int) -> None:
        mw = self.mw
        self._manual = False
        if gen != self._generation or self._closing or mw.col is None:
            # Profile closed or switched meanwhile: keep hooks balanced and
            # save what Anki would save, but leave the UI alone.
            try:
                out = fut.result()
                mw.pm.set_host_number(out.host_number)
                if out.required == out.NO_CHANGES and mw.col is not None:
                    self._start_media_monitoring()
            except Exception:
                pass
            if gen == self._generation:
                self.state = "idle"
            self._fire_did_finish()
            return

        try:
            # scheduler version may have changed
            mw.col._load_scheduler()
        except Exception:
            pass

        try:
            out = fut.result()
        except Interrupted:
            # Aborted because the user came back: nothing changed (the sync
            # rolled back). Retry at the next idle moment, without a notice.
            self.last_attempt = None
            self._finish(collection_changed=False)
            return
        except Exception as err:
            self._record_error(err)
            self._finish(collection_changed=False)
            return

        mw.pm.set_host_number(out.host_number)
        if out.new_endpoint:
            mw.pm.set_current_sync_url(out.new_endpoint)

        if out.required == out.NO_CHANGES:
            # all done; track media progress
            self._start_media_monitoring()
            self._record_success()
            self._finish(collection_changed=True)
            if out.server_message:
                showText(out.server_message, parent=mw)
            return

        if out.server_message:
            showText(out.server_message, parent=mw)

        # AnkiWeb needs a one-way full sync: let Anki ask the user.
        import aqt.sync as aqt_sync

        if out.required == out.FULL_UPLOAD and not hasattr(
            aqt_sync, "confirm_full_upload"
        ):
            # Anki < 24.06 uploads without asking and without closing open
            # windows. Don't do that unattended: wait for a manual sync.
            self.full_sync_pending = True
            self._finish(collection_changed=False)
            return

        self.state = "full_sync"
        self._watchdog = 0
        self._changed()
        try:
            aqt_sync.full_sync(mw, out, lambda: self._after_full_sync(gen))
        except Exception as err:
            log.exception("full sync dialog failed")
            self._record_error(err)
            self._finish(collection_changed=False)

    def _start_media_monitoring(self) -> None:
        media_syncer = self.mw.media_syncer
        try:
            # Anki >= 24.06: report media errors quietly, like its own
            # periodic media sync, instead of opening a message box.
            media_syncer.start_monitoring(True)
        except TypeError:
            try:
                media_syncer.start_monitoring()
            except Exception:
                pass
        except Exception:
            pass

    def _after_full_sync(self, gen: int) -> None:
        if self.state != "full_sync" or gen != self._generation:
            return
        self._finish(collection_changed=True)
        # Find out whether the user resolved it or cancelled.
        self.full_sync_pending = False
        self._verify_status()

    def _finish(self, collection_changed: bool) -> None:
        """Same steps as AnkiQt._sync_collection_and_media's completion."""
        mw = self.mw
        self.state = "idle"
        if mw.col is not None and collection_changed:
            try:
                mw.col.models._clear_cache()
            except Exception:
                pass
        self._fire_did_finish()
        if mw.col is not None:
            if collection_changed:
                self._refresh_screens()
            try:
                mw._refresh_after_sync()
            except Exception:
                try:
                    mw.toolbar.redraw()
                except Exception:
                    pass
        self._changed()

    def _refresh_screens(self) -> None:
        """Like mw.reset(), but if the Add window is open, don't tell it that
        note types and decks changed: it would switch back to the default
        note type and drop the user's choice."""
        mw = self.mw
        add_open = False
        try:
            entry = aqt.dialogs._dialogs.get("AddCards")
            add_open = bool(entry and entry[1] is not None)
        except Exception:
            pass
        if not add_open:
            mw.reset()
            return
        try:
            from anki.collection import OpChanges

            changes = OpChanges()
            for field in changes.DESCRIPTOR.fields:
                if field.name not in ("kind", "notetype", "deck"):
                    setattr(changes, field.name, True)
            gui_hooks.operation_did_execute(changes, None)
            gui_hooks.state_did_reset()
            update_undo = getattr(mw, "update_undo_actions", None)
            if update_undo:
                update_undo()
        except Exception:
            log.exception("partial refresh failed; doing a full reset")
            mw.reset()

    def _fire_did_finish(self) -> None:
        if self._will_start_fired:
            self._will_start_fired = False
            self._fire_own(gui_hooks.sync_did_finish)

    def _fire_own(self, hook) -> None:
        self._firing_own_hooks = True
        try:
            hook()
        except Exception:
            log.exception("sync hook raised")
        finally:
            self._firing_own_hooks = False

    # ------------------------------------------------------------------
    # Results

    def _record_check(self) -> None:
        now = time.time()
        self.last_check = now
        self.last_attempt = now
        self.failures = 0
        self.last_error = None

    def _record_success(self) -> None:
        now = time.time()
        self.last_sync = now
        self.last_attempt = now
        self.failures = 0
        self.last_error = None
        self.need_login = False
        self.full_sync_pending = False
        if self.conf.notify_on_success:
            tooltip(t("tooltip_synced"), parent=self.mw)

    def _record_error(self, err: Exception) -> None:
        self.last_attempt = time.time()
        if isinstance(err, Interrupted):
            return
        self.failures += 1
        if isinstance(err, SyncError) and err.kind is SyncErrorKind.AUTH:
            # Same as aqt.sync.handle_sync_error: the stored login is invalid.
            try:
                self.mw.pm.clear_sync_auth()
            except Exception:
                pass
            self.need_login = True
            self.last_error = None
            if self.conf.notify_on_error:
                tooltip(t("tooltip_login"), parent=self.mw, period=6000)
            return
        network = isinstance(err, NetworkError)
        if network:
            message = t("error_network")
        else:
            message = str(err).strip() or err.__class__.__name__
        self.last_error = message
        log.info("background sync failed: %s", message)
        if not network and self.failures >= STOP_AFTER_FAILURES:
            self.stopped_on_error = True
        notify_at = NETWORK_NOTICE_AFTER if network else 1
        if self.conf.notify_on_error and self.failures == notify_at:
            tooltip(t("tooltip_error", error=message), parent=self.mw, period=5000)

    def _changed(self) -> None:
        try:
            self.on_change()
        except Exception:
            log.exception("indicator update failed")
