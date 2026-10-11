"""Background Sync — keeps Anki in sync with AnkiWeb automatically.

Every few minutes (5 by default), when you are not in the middle of
studying, the add-on quietly runs Anki's normal sync: no progress window,
no interruption. A small cloud icon in the top toolbar shows the time of
the last sync; click it for options.

Repository: https://github.com/jorgechachaima-collab/anki-background-sync
License: GNU AGPL v3 or later.
"""

from __future__ import annotations

__version__ = "1.0.0"

from aqt import gui_hooks, mw
from aqt.qt import QAction, qconnect

from .i18n import t

_manager = None


def get_manager():
    return _manager


def _setup() -> None:
    global _manager
    if _manager is not None:
        return

    from .indicator import Indicator
    from .settings_dialog import open_settings
    from .sync_manager import BackgroundSync

    manager = BackgroundSync(mw)
    indicator = Indicator(manager)
    manager.indicator = indicator
    indicator.install()
    manager.install()
    _manager = manager

    action = QAction(t("menu_settings"), mw)
    qconnect(action.triggered, open_settings)
    mw.form.menuTools.addAction(action)
    mw.addonManager.setConfigAction(__name__, open_settings)

    # The toolbar was already drawn before we registered the tray hook.
    indicator.redraw_toolbar()


if mw is not None:
    gui_hooks.main_window_did_init.append(_setup)
