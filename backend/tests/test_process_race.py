"""A Windows launcher must not create a new interpreter after the termination snapshot."""

from types import SimpleNamespace

from errante_api.jobs import process


def test_windows_launcher_is_frozen_before_children_are_discovered(monkeypatch):
    class Member:
        def __init__(self, pid, child=None):
            self.pid, self.child = pid, child
            self.frozen = self.stopped = False

        def suspend(self):
            self.frozen = True

        def children(self, **kwargs):
            # Model the race: an unfrozen launcher has not exposed its new child yet.
            return [self.child] if self.frozen and self.child else []

        def terminate(self):
            self.stopped = True

        def wait(self, **kwargs):
            return 0

    child = Member(process.os.getpid() + 2)
    parent = Member(process.os.getpid() + 1, child)
    monkeypatch.setattr(process.sys, "platform", "win32")
    monkeypatch.setattr(process.psutil, "Process", lambda _: parent)
    monkeypatch.setattr(process.psutil, "wait_procs", lambda members, **kw: (list(members), []))
    process.kill_tree(SimpleNamespace(pid=parent.pid))
    assert parent.frozen and child.frozen
    assert parent.stopped and child.stopped


def test_windows_watchdog_does_not_suspend_itself(monkeypatch):
    calls = []

    def forbidden_suspend():
        raise AssertionError("A watchdog suspending itself would never reach termination")

    parent = SimpleNamespace(
        pid=process.os.getpid(),
        children=lambda **kw: [],
        suspend=forbidden_suspend,
        kill=lambda: calls.append("kill"),
        terminate=lambda: None,
        wait=lambda **kw: None,
    )
    monkeypatch.setattr(process.sys, "platform", "win32")
    monkeypatch.setattr(process.psutil, "Process", lambda _: parent)
    monkeypatch.setattr(process.psutil, "wait_procs", lambda members, **kw: ([], []))
    process.kill_tree(parent)
    assert calls == ["kill"]
