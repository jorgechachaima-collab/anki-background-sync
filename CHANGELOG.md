# Changelog

## 1.0.0 — 2026-10-11

First release.

- Automatic AnkiWeb sync every N minutes (default 5) without a progress window.
- Waits for N seconds of inactivity (default 60) and for the question side in the reviewer.
- Cheap status check first; full sync only when something changed.
- Full sync required → Anki's own upload/download dialog; if cancelled, no more prompts until a manual sync.
- If you touch Anki while a background sync runs, the sync is cancelled (rolled back) so the window never freezes, and retried at the next pause.
- Network errors: toolbar warning, exponential retry (1, 2, 4… min up to the interval), a notice only after 3 failures in a row. Other errors stop automatic retries after 3 attempts until "Sync now".
- The Add window keeps its note type and deck across a sync.
- Toolbar status item with menu (Sync now, Pause 1 h, Pause until restart, Settings).
- Settings window; English, Spanish, French.
- Tested on Anki 23.10, 25.02 and 26.09.3 (offscreen integration harness).
