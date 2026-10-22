import faulthandler, sys as _s

faulthandler.dump_traceback_later(55, exit=False, file=_s.stderr)
import sys, aqt
from aqt.qt import QMessageBox, QTimer, QApplication


def _w(*a, **k):
    print("MSGBOX:", a[1:3], flush=True)
    return QMessageBox.StandardButton.Ok


QMessageBox.warning = staticmethod(_w)
QMessageBox.critical = staticmethod(_w)
QMessageBox.information = staticmethod(_w)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
orig = aqt.AnkiApp.__init__


def init(self, argv):
    orig(self, argv)

    def tick():
        vis = [w for w in QApplication.topLevelWidgets() if w.isVisible()]
        print(
            "TOP:", [(w.__class__.__name__, w.windowTitle()) for w in vis], flush=True
        )
        for w in vis:
            if w.__class__.__name__ == "NoCloseDiag":
                w.accept()

    t = QTimer(self)
    t.timeout.connect(tick)
    t.start(3000)
    self._dbg = t


aqt.AnkiApp.__init__ = init
# With network access, the "Anki X has been released" box stays open and
# (correctly) blocks every background sync.
import aqt.update

aqt.update.check_for_update = lambda *a, **k: None
sys.argv = ["anki", "-b", sys.argv[1]] + sys.argv[2:]
aqt.run()
