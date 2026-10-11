"""Small status item in the right side of Anki's top toolbar, with a menu."""

from __future__ import annotations

import html
import json
import time
from typing import TYPE_CHECKING

from aqt import gui_hooks
from aqt.qt import QAction, QCursor, QMenu, qconnect

from .i18n import t

if TYPE_CHECKING:
    from .sync_manager import BackgroundSync

ELEMENT_ID = "bgsync-indicator"
COMMAND = "bgsync_menu"
CLOUD = "☁︎"  # text-style cloud, not the colour emoji

STYLE = f"""<style>
#{ELEMENT_ID} {{ font-size: 0.85em; opacity: 0.7; white-space: nowrap; }}
#{ELEMENT_ID}:hover {{ opacity: 1; }}
#{ELEMENT_ID}.bgsync-warn {{ opacity: 1; color: #d9822b; }}
#{ELEMENT_ID}.bgsync-error {{ opacity: 1; color: #d9534f; }}
#{ELEMENT_ID}.bgsync-busy {{ opacity: 1; }}
</style>"""


def _hhmm(timestamp: float) -> str:
    return time.strftime("%H:%M", time.localtime(timestamp))


class Indicator:
    def __init__(self, manager: BackgroundSync) -> None:
        self.manager = manager
        self.mw = manager.mw
        self._last_rendered: tuple[str, str, str] | None = None

    def install(self) -> None:
        gui_hooks.top_toolbar_will_set_right_tray_content.append(self._add_to_tray)
        self.manager.on_change = self.update

    # ------------------------------------------------------------------

    def render(self) -> tuple[str, str, str]:
        """Return (text, tooltip, css class) for the current state."""
        m = self.manager
        lines: list[str] = [t("addon_name")]
        css = ""

        if m.state in ("checking", "syncing", "full_sync"):
            text = f"{CLOUD} ↻"
            lines.append(t("status_syncing"))
            css = "bgsync-busy"
        elif not m.conf.enabled:
            text = f"{CLOUD} ⏸"
            lines.append(t("status_disabled"))
        elif m.is_paused():
            text = f"{CLOUD} ⏸"
            if m.paused_until == float("inf"):
                lines.append(t("status_paused_session"))
            else:
                lines.append(t("status_paused_until", time=_hhmm(m.paused_until)))
        elif m.need_login:
            text = f"{CLOUD} !"
            lines.append(t("status_login"))
            css = "bgsync-error"
        elif m.full_sync_pending:
            text = f"{CLOUD} !"
            lines.append(t("status_full_sync"))
            css = "bgsync-error"
        elif m.stopped_on_error:
            text = f"{CLOUD} !"
            lines.append(t("status_stopped", error=m.last_error or "?"))
            css = "bgsync-error"
        elif m.failures and m.last_error:
            text = f"{CLOUD} !"
            lines.append(
                t(
                    "status_error",
                    time=_hhmm(m.last_attempt or time.time()),
                    error=m.last_error,
                )
            )
            css = "bgsync-warn"
        else:
            ok = m.last_ok_time()
            if ok is None:
                text = f"{CLOUD} –"
                lines.append(t("status_never"))
            else:
                text = f"{CLOUD} {_hhmm(ok)}"
                if m.last_sync is not None and m.last_sync >= ok:
                    lines.append(t("status_synced", time=_hhmm(ok)))
                else:
                    lines.append(t("status_checked", time=_hhmm(ok)))

        if m.state == "idle" and m.conf.enabled and not m.is_paused():
            if m.waiting_for_idle:
                lines.append(t("waiting_idle"))
            elif not (m.need_login or m.full_sync_pending or m.stopped_on_error):
                remaining = m.seconds_until_due()
                if remaining < 60:
                    lines.append(t("next_soon"))
                else:
                    lines.append(t("next_in", minutes=int(round(remaining / 60))))
        lines.append(t("click_hint"))
        return text, "\n".join(lines), css

    def _add_to_tray(self, content: list[str], toolbar) -> None:
        if not self.manager.conf.show_indicator:
            return
        toolbar.link_handlers[COMMAND] = self.show_menu
        text, title, css = self.render()
        self._last_rendered = (text, title, css)
        content.append(
            STYLE
            + f'<a class="hitem {css}" tabindex="-1" id="{ELEMENT_ID}" href="#" '
            + f'title="{html.escape(title, quote=True)}" '
            + f"onclick=\"return pycmd('{COMMAND}')\">{html.escape(text)}</a>"
        )

    def update(self) -> None:
        """Refresh the toolbar item in place (cheap; skipped if unchanged)."""
        if not self.manager.conf.show_indicator:
            return
        toolbar = getattr(self.mw, "toolbar", None)
        if toolbar is None:
            return
        rendered = self.render()
        if rendered == self._last_rendered:
            return
        self._last_rendered = rendered
        text, title, css = rendered
        js = (
            "(function(){"
            f"var e=document.getElementById({json.dumps(ELEMENT_ID)});"
            "if(!e)return;"
            f"e.textContent={json.dumps(text)};"
            f"e.title={json.dumps(title)};"
            f"e.setAttribute('aria-label',{json.dumps(title)});"
            f"e.className={json.dumps(('hitem ' + css).strip())};"
            "})();"
        )
        try:
            toolbar.web.eval(js)
        except Exception:
            pass

    def redraw_toolbar(self) -> None:
        """Re-render the whole toolbar (needed when the item is shown/hidden)."""
        self._last_rendered = None
        toolbar = getattr(self.mw, "toolbar", None)
        if toolbar is not None:
            try:
                toolbar.draw()
                toolbar.redraw()
            except Exception:
                pass

    # ------------------------------------------------------------------

    def show_menu(self) -> None:
        from .settings_dialog import open_settings

        m = self.manager
        menu = QMenu(self.mw)
        _text, title, _css = self.render()
        status_lines = title.split("\n")[1:-1]
        for line in status_lines:
            info = QAction(line, menu)
            info.setEnabled(False)
            menu.addAction(info)
        menu.addSeparator()

        if m.full_sync_pending:
            label = t("action_resolve_full")
        else:
            label = t("action_sync_now")
        sync_action = menu.addAction(label)
        qconnect(sync_action.triggered, m.sync_now)
        sync_action.setEnabled(m.state == "idle")

        if m.is_paused():
            resume = menu.addAction(t("action_resume"))
            qconnect(resume.triggered, m.resume)
        elif m.conf.enabled:
            pause_1h = menu.addAction(t("action_pause_1h"))
            qconnect(pause_1h.triggered, lambda: m.pause_for(3600))
            pause_s = menu.addAction(t("action_pause_session"))
            qconnect(pause_s.triggered, m.pause_for_session)

        menu.addSeparator()
        settings = menu.addAction(t("action_settings"))
        qconnect(settings.triggered, open_settings)
        menu.exec(QCursor.pos())
