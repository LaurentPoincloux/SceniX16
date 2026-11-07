"""Une seule instance par dossier UserData."""

import subprocess
import sys
import textwrap

from scenix16.storage.instance_lock import LOCK_FILENAME, InstanceLock


def test_first_instance_gets_lock(tmp_path):
    with InstanceLock(tmp_path) as lock:
        assert lock.acquire()
        assert lock.held
        assert (tmp_path / LOCK_FILENAME).exists()


def test_second_instance_refused_then_allowed_after_release(tmp_path):
    first = InstanceLock(tmp_path)
    second = InstanceLock(tmp_path)
    assert first.acquire()
    assert not second.acquire()
    assert not second.held
    first.release()
    assert second.acquire()
    second.release()


def test_other_process_refused(tmp_path):
    """Un autre processus ne peut pas prendre le verrou tant qu'il est tenu."""
    code = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, r"{(__import__('pathlib').Path(__file__).resolve().parents[1] / 'src')}")
        from scenix16.storage.instance_lock import InstanceLock
        sys.exit(0 if InstanceLock(r"{tmp_path}").acquire() else 7)
    """)
    with InstanceLock(tmp_path) as lock:
        assert lock.acquire()
        assert subprocess.run([sys.executable, "-c", code]).returncode == 7
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0


def test_lock_released_when_process_ends(tmp_path):
    code = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, r"{(__import__('pathlib').Path(__file__).resolve().parents[1] / 'src')}")
        from scenix16.storage.instance_lock import InstanceLock
        InstanceLock(r"{tmp_path}").acquire()
        import os; os._exit(0)   # fin brutale, sans libération explicite
    """)
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0
    with InstanceLock(tmp_path) as lock:
        assert lock.acquire()
