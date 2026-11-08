"""Incrément 2.8c : réduction des animations en direct (D74, D63, D64, section 09).

Le réglage Windows « Afficher les animations » est simulé : il est relu à WM_SETTINGCHANGE et
au retour de l'application au premier plan, sans interrogation périodique. Pulsation, fondu de
l'aperçu et glissement du tri réagissent aussitôt ; la pulsation est suspendue quand le
dashboard est masqué ou la fenêtre réduite ; en cas d'échec de lecture, les animations sont
conservées. Données temporaires uniquement.
"""

import ctypes
import time
from ctypes import wintypes
from datetime import datetime

import pytest
from PySide6.QtCore import QByteArray, QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from shiboken6 import delete

from scenix16.ui import system
from scenix16.ui.animation_watch import AnimationWatcher, is_setting_change
from scenix16.ui.main_window import MainWindow
from scenix16.ui.theme import fonts
from scenix16.ui.theme.stylesheet import application_stylesheet
from test_dashboard_selection import make_userdata, pulsing

NOW = datetime(2026, 11, 7, 20, 0)
NATIVE = QByteArray(b"windows_generic_MSG")


class Setting:
    """Réglage Windows simulé, lu par le dashboard et par la surveillance."""

    def __init__(self):
        self.on = True

    def __call__(self):
        return self.on


@pytest.fixture
def setting(monkeypatch):
    s = Setting()
    monkeypatch.setattr(system, "animations_enabled", s)
    monkeypatch.setattr("scenix16.ui.dashboard.page.animations_enabled", s)
    return s


def open_window(qtbot, qapp, folder):
    fonts.load_fonts()
    qapp.setStyleSheet(application_stylesheet())
    win = MainWindow(folder, clock=lambda: NOW)               # animations : réglage système (simulé)
    qtbot.addWidget(win)
    win.resize(1280, 800)
    win.show()
    qtbot.waitExposed(win)
    win.activateWindow()
    qtbot.waitUntil(win.isActiveWindow)
    page = win.main_page
    ignore_real_pointer(page)
    page.setFocus(Qt.OtherFocusReason)
    for n in range(1, 17):
        page._pair_source(n, "key-hover", False)
        page._pair_source(n, "slot-hover", False)
    return win


def ignore_real_pointer(page):
    """Sur un écran réel, le pointeur de la souris peut survoler la fenêtre de test : le survol
    n'est pas l'objet de ces tests, il est neutralisé (focus clavier et sélection seulement)."""
    original = page._pair_source

    def without_hover(number, source, on):
        if not source.endswith("hover"):
            original(number, source, on)
    page._pair_source = without_hover
    for n in range(1, 17):
        page.key(n).underMouse = lambda: False
        page.slot(n).underMouse = lambda: False


@pytest.fixture
def win(qtbot, qapp, tmp_path, setting):
    return open_window(qtbot, qapp, make_userdata(tmp_path, range(0, 40, 2)))   # A01 : jour, sélectionné


def settings_message(win, msg_id=system.WM_SETTINGCHANGE, wparam=system.SPI_SETCLIENTAREAANIMATION):
    """Message natif tel que Qt le transmet au filtre de l'application."""
    msg = wintypes.MSG()
    msg.message = msg_id
    msg.wParam = wparam
    assert win.animation_watch.native_filter.nativeEventFilter(NATIVE, ctypes.addressof(msg)) == (False, 0)


def switch(win, setting, on):
    """Windows modifie le réglage et diffuse WM_SETTINGCHANGE."""
    setting.on = on
    settings_message(win)


def full_opacity(page, n):
    return page.key(n)._led_opacity == 1.0 and page.slot(n)._dot_opacity == 1.0


# --- lecture du réglage et repli ----------------------------------------------------------------------

def test_read_failure_keeps_animations(monkeypatch):
    def broken():
        raise OSError("API indisponible")
    monkeypatch.setattr(system, "_read_client_area_animation", broken)
    assert system.animations_enabled() is True
    monkeypatch.setattr(system, "_read_client_area_animation", lambda: None)   # appel refusé
    assert system.animations_enabled() is True
    monkeypatch.setattr(system, "_read_client_area_animation", lambda: False)
    assert system.animations_enabled() is False


def test_watcher_falls_back_to_animations_when_reader_fails(qapp):
    def broken():
        raise RuntimeError("lecture impossible")
    watch = AnimationWatcher(read=broken)
    assert watch.enabled is True and watch.refresh() is False


def test_watcher_emits_only_on_real_change(qapp):
    value = {"on": True}
    watch = AnimationWatcher(read=lambda: value["on"])
    seen = []
    watch.changed.connect(seen.append)
    assert watch.refresh() is False
    value["on"] = False
    assert watch.refresh() is True and watch.refresh() is False
    value["on"] = True
    assert watch.refresh() is True
    assert seen == [False, True]


def test_no_polling_timer(win):
    assert not win.animation_watch.findChildren(QTimer)          # aucune interrogation périodique


def test_native_filter_removed_with_its_watcher(qapp, monkeypatch):
    import scenix16.ui.animation_watch as watch_module
    removed = []
    original = watch_module._remove_filter
    monkeypatch.setattr(watch_module, "_remove_filter",
                        lambda app, f: (removed.append(f), original(app, f)))
    watch = AnimationWatcher(read=lambda: True)
    native_filter = watch.native_filter
    assert native_filter is not None
    delete(watch)                                                  # destruction de la surveillance
    assert removed == [native_filter]                              # filtre retiré de l'application


def test_only_wm_settingchange_is_recognized():
    msg = wintypes.MSG()
    msg.message = system.WM_SETTINGCHANGE
    assert is_setting_change(NATIVE, ctypes.addressof(msg))
    msg.message = 0x000F                                          # WM_PAINT
    assert not is_setting_change(NATIVE, ctypes.addressof(msg))
    assert not is_setting_change(QByteArray(b"xcb_generic_event_t"), ctypes.addressof(msg))
    assert not is_setting_change(NATIVE, 0)


# --- changement en direct : pulsation ----------------------------------------------------------------------

def test_pulse_stops_and_restarts_with_windows_setting(win, setting):
    page = win.main_page
    assert pulsing(page) == [1]
    switch(win, setting, False)
    assert pulsing(page) == [] and full_opacity(page, 1)            # point fixe, pleine opacité
    assert page.selected_position() == 1 and page.is_emphasized(1)  # la sélection reste visible
    switch(win, setting, True)
    assert pulsing(page) == [1]
    assert full_opacity(page, 1)                                    # reprise sans saut : pleine opacité


def test_other_settings_messages_do_not_disturb(win, setting):
    page = win.main_page
    settings_message(win, wparam=0x0014)                            # autre réglage, valeur inchangée
    settings_message(win, msg_id=0x000F)                            # autre message
    assert pulsing(page) == [1]


def test_activation_rereads_setting(win, setting, qapp):
    page = win.main_page
    setting.on = False                                              # message manqué
    assert pulsing(page) == [1]
    qapp.sendEvent(win, QEvent(QEvent.ActivationChange))            # l'application redevient active
    assert pulsing(page) == []
    setting.on = True
    qapp.sendEvent(win, QEvent(QEvent.ActivationChange))
    assert pulsing(page) == [1]


def test_real_windows_message_reaches_the_window(win, setting, qtbot):
    if QGuiApplication.platformName() != "windows":
        pytest.skip("message Windows réel : écran réel uniquement")
    page = win.main_page
    setting.on = False
    ctypes.windll.user32.SendMessageW(wintypes.HWND(int(win.winId())), system.WM_SETTINGCHANGE,
                                      system.SPI_SETCLIENTAREAANIMATION, 0)
    qtbot.waitUntil(lambda: pulsing(page) == [])


def test_reduced_setting_at_launch(qtbot, qapp, tmp_path, setting):
    setting.on = False
    win = open_window(qtbot, qapp, make_userdata(tmp_path, range(0, 40, 2)))
    page = win.main_page
    assert page.selected_position() == 1 and pulsing(page) == [] and full_opacity(page, 1)
    assert win.animation_watch.enabled is False


# --- changement en direct : fondu et glissement en cours ------------------------------------------------

def test_fade_in_progress_finishes_at_full_opacity(win, setting, qtbot):
    page = win.main_page
    page.key(2).setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(page.preview.fading)
    switch(win, setting, False)
    assert not page.preview.fading() and page.preview_visible()
    assert page.preview._effect.opacity() == 1.0


def test_glide_in_progress_finishes_at_final_position(win, setting, qtbot):
    page = win.main_page
    win.toggle_sort()
    assert page.reorder is not None and page.reorder.running
    overlay = page.reorder
    switch(win, setting, False)
    assert page.reorder is None and not overlay.running             # position finale immédiate
    names = [page.slot(n).name_text() for n in range(1, 17)]
    assert names[0] == "Concert 20"                                 # plus récent d'abord, banque A


def test_next_fade_and_glide_are_instant_when_reduced(win, setting, qtbot):
    page = win.main_page
    switch(win, setting, False)
    start = time.monotonic()
    page.key(3).setFocus(Qt.TabFocusReason)
    qtbot.wait(200)
    assert not page.preview_visible()                               # délai de 350 ms conservé (A6)
    qtbot.waitUntil(page.preview_visible)
    assert time.monotonic() - start >= 0.33
    assert not page.preview.fading() and page.preview._effect.opacity() == 1.0
    win.toggle_sort()
    assert page.reorder is None                                     # aucun glissement


def test_animations_work_normally_when_enabled(win, setting, qtbot):
    page = win.main_page
    assert pulsing(page) == [1]
    page.key(2).setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(page.preview_visible)
    assert page.preview.fading() or page.preview._effect.opacity() > 0  # fondu de 120 ms
    win.toggle_sort()
    assert page.reorder is not None and page.reorder.running        # glissement de 180 ms
    qtbot.waitUntil(lambda: page.reorder is None, timeout=2000)


def test_fade_and_glide_resume_after_reenabling(win, setting, qtbot):
    page = win.main_page
    switch(win, setting, False)
    switch(win, setting, True)
    page.key(4).setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(page.preview.fading)
    win.toggle_sort()
    assert page.reorder is not None


# --- sélection, focus et aperçu conservés --------------------------------------------------------------------

def test_selection_focus_and_preview_preserved(win, setting, qtbot):
    page = win.main_page
    page.key(3).setFocus(Qt.TabFocusReason)
    qtbot.waitUntil(lambda: page.preview_visible() and not page.preview.fading())
    for on in (False, True):
        switch(win, setting, on)
        assert page.key(3).hasFocus() and page.selected_position() == 3
        assert page.preview_visible() and page.preview.number == 3
    assert pulsing(page) == [3]


# --- suspension quand le dashboard est masqué ou la fenêtre réduite (A2) ----------------------------------------

def test_pulse_suspended_on_sheet_then_resumes(win, setting, qtbot):
    page = win.main_page
    page.key(2).setFocus(Qt.TabFocusReason)
    qtbot.keyClick(page.key(2), Qt.Key_Return)
    assert win.pages.currentWidget() is win.sheet_page
    assert pulsing(page) == [] and full_opacity(page, 2)
    qtbot.keyClick(win.sheet_page, Qt.Key_Escape)
    assert win.pages.currentWidget() is win.main_page
    assert pulsing(page) == [2] and page.key(2).hasFocus()


def test_pulse_suspended_on_settings_then_resumes(win, setting):
    page = win.main_page
    win.show_settings()
    assert pulsing(page) == []
    win.show_main()
    assert pulsing(page) == [1]


def test_pulse_suspended_when_minimized_then_resumes(win, setting, qtbot):
    page = win.main_page
    win.showMinimized()
    qtbot.waitUntil(lambda: bool(win.windowState() & Qt.WindowMinimized))
    assert pulsing(page) == []
    win.showNormal()
    qtbot.waitUntil(lambda: not win.windowState() & Qt.WindowMinimized)
    qtbot.waitUntil(lambda: pulsing(page) == [1])


def test_hidden_dashboard_stays_suspended_when_setting_returns(win, setting):
    page = win.main_page
    switch(win, setting, False)
    win.show_settings()
    switch(win, setting, True)                                      # réglage rétabli, dashboard masqué
    assert pulsing(page) == []
    win.show_main()
    assert pulsing(page) == [1]


def test_no_pulse_without_selection(win, setting):
    page = win.main_page
    page.select_concert(None)
    switch(win, setting, False)
    switch(win, setting, True)
    assert pulsing(page) == []


# --- redessin limité au point d'état (A3) --------------------------------------------------------------------

class PaintSpy(QObject):
    def __init__(self, widget):
        super().__init__()
        self.rects = []
        widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Paint:
            self.rects.append(event.rect())
        return False


def test_pulse_repaints_only_the_status_point(win, setting, qtbot):
    page = win.main_page
    key, slot = page.key(1), page.slot(1)
    qtbot.wait(200)                                                  # rendus de mise en place terminés
    key_spy, slot_spy = PaintSpy(key), PaintSpy(slot)
    qtbot.wait(300)                                                  # plusieurs images de pulsation
    assert key_spy.rects and slot_spy.rects
    assert all(key.led_rect().contains(r) for r in key_spy.rects)
    assert all(slot.dot_rect().contains(r) for r in slot_spy.rects)
    assert key.led_rect().width() < key.width() and slot.dot_rect().width() < slot.width() // 4


def test_pulse_keeps_its_cadence(win, setting):
    key = win.main_page.key(1)
    assert key._pulse.duration() == 2400 and key._pulse.loopCount() == -1
