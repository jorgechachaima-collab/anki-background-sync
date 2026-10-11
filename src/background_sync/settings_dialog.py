"""Settings window (Tools → Background Sync…, or the add-on's Config button)."""

from __future__ import annotations

from aqt import mw
from aqt.qt import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    qconnect,
)
from aqt.utils import disable_help_button

from . import config as config_mod
from .i18n import t


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent or mw)
        self.setWindowTitle(t("dlg_title"))
        disable_help_button(self)
        conf = config_mod.load()

        self.enabled = QCheckBox(t("dlg_enabled"))
        self.enabled.setChecked(conf.enabled)

        self.interval = QSpinBox()
        self.interval.setRange(config_mod.MIN_INTERVAL_MIN, config_mod.MAX_INTERVAL_MIN)
        self.interval.setSuffix(t("dlg_interval_suffix"))
        self.interval.setValue(conf.interval_minutes)

        self.idle = QSpinBox()
        self.idle.setRange(config_mod.MIN_IDLE_S, config_mod.MAX_IDLE_S)
        self.idle.setSingleStep(15)
        self.idle.setSuffix(t("dlg_idle_suffix"))
        self.idle.setValue(conf.idle_seconds)
        self.idle.setToolTip(t("dlg_idle_help"))

        self.show_indicator = QCheckBox(t("dlg_show_indicator"))
        self.show_indicator.setChecked(conf.show_indicator)
        self.notify_errors = QCheckBox(t("dlg_notify_errors"))
        self.notify_errors.setChecked(conf.notify_on_error)
        self.notify_success = QCheckBox(t("dlg_notify_success"))
        self.notify_success.setChecked(conf.notify_on_success)

        form = QFormLayout()
        form.addRow(t("dlg_interval"), self.interval)
        idle_label = QLabel(t("dlg_idle"))
        idle_label.setToolTip(t("dlg_idle_help"))
        form.addRow(idle_label, self.idle)

        help_label = QLabel(t("dlg_idle_help"))
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: gray; font-size: 11px;")
        notes = QLabel(t("dlg_notes"))
        notes.setWordWrap(True)
        notes.setStyleSheet("color: gray; font-size: 11px;")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        qconnect(buttons.accepted, self.accept)
        qconnect(buttons.rejected, self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.enabled)
        layout.addLayout(form)
        layout.addWidget(help_label)
        layout.addSpacing(6)
        layout.addWidget(self.show_indicator)
        layout.addWidget(self.notify_errors)
        layout.addWidget(self.notify_success)
        layout.addSpacing(6)
        layout.addWidget(notes)
        layout.addWidget(buttons)

        qconnect(self.enabled.toggled, self._update_enabled)
        self._update_enabled(conf.enabled)
        self.setMinimumWidth(460)

    def _update_enabled(self, on: bool) -> None:
        self.interval.setEnabled(on)
        self.idle.setEnabled(on)

    def accept(self) -> None:
        old = config_mod.load()
        new = config_mod.Config(
            enabled=self.enabled.isChecked(),
            interval_minutes=self.interval.value(),
            idle_seconds=self.idle.value(),
            show_indicator=self.show_indicator.isChecked(),
            notify_on_error=self.notify_errors.isChecked(),
            notify_on_success=self.notify_success.isChecked(),
        )
        config_mod.save(new)
        from . import get_manager

        manager = get_manager()
        if manager is not None:
            manager.reload_config()
            if old.show_indicator != new.show_indicator and manager.indicator:
                manager.indicator.redraw_toolbar()
        super().accept()


def open_settings() -> bool:
    SettingsDialog(mw).exec()
    # Tell the add-on manager we handled the Config button ourselves.
    return True
