# Background Sync (Anki add-on) — notes for the next session

Add-on that syncs Anki ↔ AnkiWeb automatically in the background. Owner: Jorge (not a programmer: give copy-paste Terminal steps). To be published on AnkiWeb + GitHub (`jorgechachaima-collab/anki-background-sync`).

## Decisions taken with Jorge (2026-10-11)
- What: Anki ↔ AnkiWeb only (not nanoanki, not external sources).
- Trigger: every N minutes; default **5** (range 2–240).
- While studying: wait for inactivity (default **60 s**, range 15–900). Also waits while the answer side is showing (up to 10 min idle).
- Media: follow Anki's own preference (`pm.media_syncing_enabled()`).
- Full sync required: **ask** with Anki's own dialog (`aqt.sync.full_sync`). If cancelled → `full_sync_pending`, no more prompts until a manual sync.
- Network errors: no popups; toolbar warning, backoff 1/2/4… min (capped at interval), tooltip only after 3 consecutive failures (avoid noise after wake from sleep). Other errors: stop auto-retry after 3 until "Sync now".
- Visibility: discreet toolbar item (right tray, "☁ HH:MM"), click → menu (Sync now, Pause 1 h, Pause until restart, Settings).
- Languages: en / es / fr (follows Anki's language).
- Publish: AnkiWeb + GitHub; license AGPL-3.0-or-later (same as Anki).
- Min Anki: 23.10 (manifest `min_point_version` 231000). Jorge uses 25.02.

## Technical choices (why)
- First `col.sync_status(auth)` with `uses_collection=False` (cheap; no network if local changes; remote check cached 300 s by backend). Only `NORMAL_SYNC`/`FULL_SYNC` trigger `col.sync_collection`.
- The sync itself mirrors `aqt.sync.sync_collection` + `AnkiQt._sync_collection_and_media` without the progress window: `_load_scheduler`, `set_host_number`, `set_current_sync_url`, server message, `media_syncer.start_monitoring(True)` (True = quiet media errors on ≥24.06; fallback without arg on 23.10), `models._clear_cache`, `sync_will_start/sync_did_finish` hooks, reset, `_refresh_after_sync`.
- Backend holds the collection lock during the whole sync → any keyboard/mouse/touch input during OUR (non-manual) sync calls `col.abort_sync()` (rolls back, retried at next idle) so Anki never freezes.
- If the Add window is open, the refresh omits `notetype`/`deck` changes (otherwise AddCards resets to the default note type).
- On Anki < 24.06, FULL_UPLOAD is not started unattended (old Anki uploads without confirmation and without closing windows) → pending.
- Watchdog: if state is `full_sync` (or an Anki sync started but never finished) and no dialog/progress is visible for 3 ticks → recover.
- Generation counter: callbacks from a previous profile are ignored.
- Anki's own sync finishing does NOT count as success: we re-check `sync_status`.
- Logging: `addonManager.get_logger` (≥24.06) or stdout. NEVER stderr (on 23.10 stderr opens Anki's error window — found in testing).
- Known/accepted: after a sync in the reviewer, the current card is shown again (audio replays) like after a manual sync; a sync clears undo (Anki behaviour). Documented in README.

## Testing (done in the cloud container; no Anki on Jorge's side needed)
`tests/run_anki.py` launches real Anki offscreen; `tests/probe_addon.py` is a probe add-on that fakes AnkiWeb (patches `col.sync_status`/`col.sync_collection`) and checks 57 scenarios. Result 2026-10-11: **57/57 on 25.02 and 26.09.3, 56/56 on 23.10** (one check is version-specific).
Setup: venvs with `aqt==X anki==X` + matching PyQt6/WebEngine (23.10 needs python3.11 + PyQt6 6.6.1); env `QT_QPA_PLATFORM=offscreen QTWEBENGINE_CHROMIUM_FLAGS=--no-sandbox`. First run auto-accepts the language dialog (run_anki.py patches QMessageBox).
An adversarial review by a sub-agent was done; all its relevant findings were fixed (see git history of v1.0.0).

## Build / install
- `bash build.sh` (or double-click `build.command` on macOS) → `dist/background_sync-<version>.ankiaddon`. Double-click that file to install in Anki.
- Version lives in `src/background_sync/__init__.py` (`__version__`) + CHANGELOG.md.
- AnkiWeb page text: `ankiweb_description.html`. Screenshots: `docs/`.

## Status
- v1.0.0 written and tested 2026-10-11. Local git repo committed.
- Pending: create GitHub repo + push (needs a token from Jorge; cloud proxy blocks push — push from the Mac VM as for nanoanki), Jorge's real-life test on Anki 25.02, then AnkiWeb upload (Jorge must do it at ankiweb.net/shared/addons logged in).
