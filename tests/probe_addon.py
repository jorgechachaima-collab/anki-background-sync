import time, traceback
from aqt import mw, gui_hooks
from aqt.qt import QTimer, QApplication
from anki.sync import SyncStatus, SyncOutput
from anki.sync_pb2 import SyncAuth
from anki.errors import NetworkError, SyncError, SyncErrorKind, Interrupted

R = []


def check(name, cond, extra=""):
    R.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name, extra, flush=True)


calls = {"status": 0, "sync": 0}
behaviour = {"status": SyncStatus.NORMAL_SYNC, "sync": "ok"}


def fake_status(auth):
    return SyncStatus(required=behaviour["status"])


abort_flag = []


def fake_sync(auth, media):
    calls["sync"] += 1
    b = behaviour["sync"]
    if b == "slow":
        for _ in range(60):
            time.sleep(0.05)
            if abort_flag:
                abort_flag.clear()
                raise Interrupted("", 0, "", "")
        return SyncOutput(required=SyncOutput.NO_CHANGES, host_number=3)
    time.sleep(0.5)
    if b == "server":
        raise SyncError("AnkiWeb is under maintenance", 0, "", "", SyncErrorKind.OTHER)
    if b == "upload":
        return SyncOutput(required=SyncOutput.FULL_UPLOAD, host_number=3)
    if b == "ok":
        return SyncOutput(required=SyncOutput.NO_CHANGES, host_number=3)
    if b == "network":
        raise NetworkError("net down", 0, "", "")
    if b == "auth":
        raise SyncError("bad auth", 0, "", "", SyncErrorKind.AUTH)
    if b == "full":
        return SyncOutput(required=SyncOutput.FULL_SYNC, host_number=3)


hooks = {"will": 0, "did": 0}
gui_hooks.sync_will_start.append(lambda: hooks.__setitem__("will", hooks["will"] + 1))
gui_hooks.sync_did_finish.append(lambda: hooks.__setitem__("did", hooks["did"] + 1))


def dom(cb):
    mw.toolbar.web.evalWithCallback(
        "var e=document.getElementById('bgsync-indicator'); e? (e.textContent+'|'+e.className+'|'+e.title) : 'none'",
        cb,
    )


def steps():
    import background_sync

    m = background_sync.get_manager()
    check("manager created", m is not None)
    check(
        "tools menu entry",
        any("Background Sync" in a.text() for a in mw.form.menuTools.actions()),
    )
    auth = SyncAuth(hkey="k")
    mw.pm.sync_auth = lambda: auth
    mw.pm.clear_sync_auth = lambda: setattr(mw.pm, "sync_auth", lambda: None)
    mw.col.sync_status = fake_status
    mw.col.sync_collection = fake_sync
    mw.media_syncer.start_monitoring = lambda *a, **k: None
    m.conf.idle_seconds = 0
    m.conf.notify_on_success = True
    m._timer.stop()
    calls["status"] = 0
    _orig_check = m._check_status

    def counting_check():
        calls["status"] += 1
        _orig_check()

    m._check_status = counting_check
    # add a card so the reviewer can open
    note = mw.col.newNote()
    note["Front"] = "q"
    note["Back"] = "a"
    mw.col.addNote(note)

    # 1. not due -> nothing
    m._tick()
    yield 300
    check("not due: no status call", calls["status"] == 0)

    # 2. due + normal sync
    m.session_start = 0
    m._tick()
    yield 2500
    check("status checked", calls["status"] == 1)
    check("sync ran", calls["sync"] == 1)
    check("state idle after", m.state == "idle", m.state)
    check("last_sync set", m.last_sync is not None)
    check("hooks fired", hooks["will"] == 1 and hooks["did"] == 1, hooks)
    check(
        "host number saved",
        mw.pm.profile.get("hostNum") == 3,
        mw.pm.profile.get("hostNum"),
    )
    out = {}
    dom(lambda v: out.setdefault("d", v))
    yield 500
    check(
        "indicator shows time",
        out.get("d", "").startswith("☁︎ ") and ":" in out["d"].split("|")[0],
        out.get("d"),
    )

    # 3. right after: not due
    m._tick()
    yield 300
    check("not due after success", calls["status"] == 1)

    # 4. due again, no changes -> only check
    behaviour["status"] = SyncStatus.NO_CHANGES
    m.last_sync = 0
    m.last_attempt = 0
    m.last_check = None
    m._tick()
    yield 1000
    check("no-changes: status only", calls["status"] == 2 and calls["sync"] == 1, calls)
    check("last_check set", m.last_check is not None)

    # 5. user active -> waits
    behaviour["status"] = SyncStatus.NORMAL_SYNC
    m.last_check = 0
    m.last_sync = 0
    m.last_attempt = 0
    m.conf.idle_seconds = 60
    m._note_activity()
    m._tick()
    yield 300
    check(
        "active user: no check",
        calls["status"] == 2 and m.waiting_for_idle,
        (calls, m.waiting_for_idle),
    )
    m.conf.idle_seconds = 0

    # 6. modal dialog -> blocked
    from aqt.qt import QDialog

    d = QDialog(mw)
    d.setModal(True)
    d.show()
    yield 300
    m._tick()
    yield 300
    check("modal open: no check", calls["status"] == 2)
    d.done(0)
    d.hide()
    d.deleteLater()
    yield 300

    # 7. network error
    behaviour["sync"] = "network"
    m._tick()
    yield 2000
    check(
        "network error recorded",
        m.failures == 1 and m.last_error,
        (m.failures, m.last_error),
    )
    check("did_finish fired on error", hooks["did"] == 2, hooks)
    check(
        "retry scheduled ~60s", 50 < m.seconds_until_due() <= 60, m.seconds_until_due()
    )
    dom(lambda v: out.__setitem__("d", v))
    yield 500
    check("indicator warn", "bgsync-warn" in out["d"], out["d"])

    # 8. recovery
    behaviour["sync"] = "ok"
    m.last_attempt = 0
    m._tick()
    yield 2000
    check(
        "recovered",
        m.failures == 0 and m.last_error is None and calls["sync"] == 3,
        (m.failures, calls),
    )

    # 9. full sync -> Anki dialog; cancel it -> pending
    behaviour["sync"] = "full"
    m.last_sync = 0
    m.last_attempt = 0
    m._tick()
    yield 2000
    check("full sync state", m.state == "full_sync", m.state)
    vis = [w for w in QApplication.topLevelWidgets() if w.isVisible() and w is not mw]
    print(
        "VISIBLE",
        [(w.__class__.__name__, getattr(w, "windowTitle", lambda: "")()) for w in vis],
        flush=True,
    )
    check("anki full-sync dialog shown", len(vis) >= 1)
    behaviour["status"] = SyncStatus.FULL_SYNC
    from aqt.qt import QMessageBox, QDialog as _D

    for w in vis:
        # click the cancel button (third)
        btns = w.findChildren(
            __import__("aqt.qt", fromlist=["QPushButton"]).QPushButton
        )
        print("BUTTONS", [b.text() for b in btns], flush=True)
        for b in btns:
            if "ancel" in b.text():
                b.click()
    yield 2000
    check("after cancel: idle", m.state == "idle", m.state)
    check("full sync pending", m.full_sync_pending)
    s_before = calls["sync"]
    m.last_attempt = 0
    m.last_sync = 0
    m.last_check = 0
    m._tick()
    yield 1500
    check(
        "pending: not asked again",
        calls["sync"] == s_before and m.state == "idle",
        (calls, m.state),
    )
    dom(lambda v: out.__setitem__("d", v))
    yield 500
    check("indicator error for full sync", "bgsync-error" in out["d"], out["d"])

    # 10. Anki's own sync finishing re-verifies status instead of assuming success
    gui_hooks.sync_will_start()
    gui_hooks.sync_did_finish()
    yield 800
    check("external finish re-verifies (still full -> pending)", m.full_sync_pending)
    behaviour["status"] = SyncStatus.NO_CHANGES
    gui_hooks.sync_will_start()
    gui_hooks.sync_did_finish()
    yield 800
    check(
        "external finish re-verifies (now clean)",
        not m.full_sync_pending and m.last_sync,
        (m.full_sync_pending, m.last_sync),
    )

    # 11. auth error
    behaviour["status"] = SyncStatus.NORMAL_SYNC
    behaviour["sync"] = "auth"
    m.last_attempt = 0
    m.last_sync = 0
    m.last_check = 0
    m._tick()
    yield 2000
    check("auth error -> need_login", m.need_login, (m.need_login, m.last_error))
    m._tick()
    yield 300
    check("no auth: stays need_login, no calls", m.need_login and m.state == "idle")

    # 12. pause
    mw.pm.sync_auth = lambda: auth
    behaviour["sync"] = "ok"
    m.pause_for(3600)
    st = calls["status"]
    m.last_attempt = 0
    m.last_sync = 0
    m.last_check = 0
    m._tick()
    yield 300
    check("paused: nothing", calls["status"] == st)
    dom(lambda v: out.__setitem__("d", v))
    yield 500
    check("indicator paused", "⏸" in out["d"], out["d"])
    m.resume()

    # 13. review with answer showing
    m.conf.idle_seconds = 0
    mw.moveToState("review")
    yield 1500
    print("STATE", mw.state, getattr(mw.reviewer, "state", None), flush=True)
    if mw.state == "review":
        mw.reviewer.state = "answer"
        st = calls["status"]
        m._tick()
        yield 300
        check("answer showing: wait", calls["status"] == st)
        mw.reviewer.state = "question"
        m._tick()
        yield 2500
        check(
            "sync while question shown",
            calls["status"] == st + 1 and m.state == "idle" and mw.state == "review",
            (calls, m.state, mw.state),
        )
    mw.moveToState("deckBrowser")
    yield 500

    # 14. settings dialog
    from background_sync.settings_dialog import SettingsDialog

    dlg = SettingsDialog(mw)
    dlg.interval.setValue(12)
    dlg.show_indicator.setChecked(False)
    dlg.accept()
    yield 1500
    check(
        "config saved",
        mw.addonManager.getConfig("background_sync")["interval_minutes"] == 12,
    )
    check("manager reloaded", m.conf.interval_minutes == 12)
    dom(lambda v: out.__setitem__("d", v))
    yield 800
    check("indicator hidden", out["d"] == "none", out["d"])
    dlg = SettingsDialog(mw)
    dlg.show_indicator.setChecked(True)
    dlg.interval.setValue(5)
    dlg.accept()
    yield 1500
    dom(lambda v: out.__setitem__("d", v))
    yield 800
    check("indicator back", out["d"] != "none", out["d"][:30])

    # 15. menu builds (don't exec)
    from aqt.qt import QMenu

    orig = QMenu.exec
    QMenu.exec = lambda self, *a: print(
        "MENU", [a.text() for a in self.actions()], flush=True
    )
    m.indicator.show_menu()
    QMenu.exec = orig
    check("menu ok", True)

    # 16. i18n
    import anki.lang
    from background_sync.i18n import t

    anki.lang.current_lang = "fr_FR"
    fr = t("action_sync_now")
    anki.lang.current_lang = "es_ES"
    es = t("action_sync_now")
    anki.lang.current_lang = "de_DE"
    de = t("action_sync_now")
    anki.lang.current_lang = "en"
    check(
        "i18n",
        (fr, es, de) == ("Synchroniser maintenant", "Sincronizar ahora", "Sync now"),
        (fr, es, de),
    )

    # 17. profile close while syncing -> abort called, no crash
    behaviour["sync"] = "ok"
    aborted = []
    mw.col.abort_sync = lambda: aborted.append(1)
    m._start_sync()
    yield 100
    print("state before close", m.state, flush=True)
    m._on_profile_close()
    check("abort on close", m.state != "syncing" or aborted, (m.state, aborted))
    yield 1500
    m._on_profile_open()

    # 18. user comes back during a sync -> aborted, no failure, retried later
    m.conf.idle_seconds = 15
    m._last_activity = time.monotonic() - 100
    mw.col.abort_sync = lambda: abort_flag.append(1)
    behaviour["status"] = SyncStatus.NORMAL_SYNC
    behaviour["sync"] = "slow"
    m.session_start = 0
    m.last_attempt = 0
    m.last_sync = 0
    m.last_check = 0
    m.failures = 0
    did_before = hooks["did"]
    m._tick()
    yield 600
    check("slow sync running", m.state == "syncing", m.state)
    m._note_activity()
    yield 1200
    check(
        "aborted on activity",
        m.state == "idle" and m.failures == 0 and m.last_error is None,
        (m.state, m.failures, m.last_error),
    )
    check("did_finish after abort", hooks["did"] == did_before + 1, hooks)
    check(
        "retry due right away after abort",
        m.seconds_until_due() == 0,
        m.seconds_until_due(),
    )
    m._tick()
    yield 300
    check("but waits for idle", m.state == "idle" and m.waiting_for_idle)
    m.conf.idle_seconds = 0

    # 19. non-network errors stop auto retries after 3
    behaviour["sync"] = "server"
    for _ in range(3):
        m.last_attempt = 0
        m._tick()
        yield 1300
    check(
        "stopped after 3 server errors",
        m.stopped_on_error and m.failures == 3,
        (m.stopped_on_error, m.failures, m.last_error),
    )
    s0 = calls["status"]
    m.last_attempt = 0
    m._tick()
    yield 300
    check("no more attempts when stopped", calls["status"] == s0)
    dom(lambda v: out.__setitem__("d", v))
    yield 500
    check(
        "indicator shows stopped",
        "bgsync-error" in out["d"] and "maintenance" in out["d"],
        out["d"],
    )
    behaviour["sync"] = "ok"
    m.sync_now()
    yield 1300
    check(
        "sync now clears stop",
        not m.stopped_on_error and m.failures == 0 and m.state == "idle",
        (m.stopped_on_error, m.failures),
    )

    # 20. FULL_UPLOAD
    import aqt.sync as aqt_sync

    behaviour["sync"] = "upload"
    m.last_attempt = 0
    m.last_sync = 0
    m.last_check = 0
    m._tick()
    yield 1500
    if hasattr(aqt_sync, "confirm_full_upload"):
        vis = [
            w
            for w in QApplication.topLevelWidgets()
            if w.isVisible() and w is not mw and w.__class__.__name__ != "CustomLabel"
        ]
        check(
            "upload: confirmation dialog shown (>=24.06)",
            m.state == "full_sync" and vis,
            (m.state, vis),
        )
        behaviour["status"] = SyncStatus.FULL_SYNC
        from aqt.qt import QPushButton

        for w in vis:
            btns = w.findChildren(QPushButton)
            print("UPLOAD BUTTONS", [b.text() for b in btns], flush=True)
            # default button 0 is "No" in ask_user_dialog(confirm); click the 2nd (No/cancel)
            for b in btns:
                if b.text().replace("&", "").lower() in ("no", "cancel"):
                    b.click()
                    break
        yield 1500
        check(
            "upload cancelled -> pending",
            m.state == "idle" and m.full_sync_pending,
            (m.state, m.full_sync_pending),
        )
    else:
        check(
            "upload on old Anki: not started unattended",
            m.state == "idle" and m.full_sync_pending,
            (m.state, m.full_sync_pending),
        )
    m.full_sync_pending = False

    # 21. watchdog: full_sync state with no dialog -> recovers
    behaviour["status"] = SyncStatus.NO_CHANGES
    m.state = "full_sync"
    for _ in range(3):
        m._tick()
        yield 100
    yield 800
    check("watchdog recovered", m.state == "idle", m.state)
    m._external_sync_running = True
    for _ in range(3):
        m._tick()
        yield 100
    check("watchdog clears external flag", not m._external_sync_running)

    # 22. Add window keeps chosen note type across a sync
    import aqt

    behaviour["status"] = SyncStatus.NORMAL_SYNC
    behaviour["sync"] = "ok"
    add = aqt.dialogs.open("AddCards", mw)
    yield 1500
    cloze = mw.col.models.by_name("Cloze")
    add.notetype_chooser.selected_notetype_id = cloze["id"]
    yield 800
    before = add.notetype_chooser.selected_notetype_id
    m.last_attempt = 0
    m.last_sync = 0
    m.last_check = 0
    m._tick()
    yield 2000
    check("sync with Add window open", m.last_sync and m.state == "idle", m.state)
    check(
        "Add window keeps note type",
        add.notetype_chooser.selected_notetype_id == before == cloze["id"],
        (add.notetype_chooser.selected_notetype_id, before),
    )
    add.close()
    yield 1500
    for w in QApplication.topLevelWidgets():
        if (
            w.isVisible()
            and w is not mw
            and w.__class__.__name__ not in ("CustomLabel",)
        ):
            print("CLOSING", w.__class__.__name__, flush=True)
            try:
                w.reject()
            except Exception:
                w.close()
    yield 800

    extra = [
        w.__class__.__name__
        for w in QApplication.topLevelWidgets()
        if w.isVisible() and w is not mw and w.__class__.__name__ != "CustomLabel"
    ]
    check("no stray/error dialogs", not extra, extra)
    fails = [n for n, ok in R if not ok]
    print(
        "SUMMARY", len(R) - len(fails), "/", len(R), "passed; fails:", fails, flush=True
    )


def run():
    gen = steps()

    def nxt():
        try:
            delay = next(gen)
            QTimer.singleShot(delay, nxt)
        except StopIteration:
            QTimer.singleShot(300, mw.app.quit)
        except Exception:
            traceback.print_exc()
            QTimer.singleShot(300, mw.app.quit)

    nxt()


gui_hooks.main_window_did_init.append(lambda: QTimer.singleShot(2500, run))
