"""Preselected input boundary for existing scheduler/API unit tests.

The real HWND, PID, focus and transport protections are tested separately in
test_targeted_input.py; these doubles only record routine behavior.
"""

import config


class FakeTargetMixin:
    def configure(self, cfg):
        self.cfg = cfg
        return self

    def set_logger(self, log):
        pass

    def blocked_reason(self):
        return None if config.matches_window(self.cfg, self.window) else "sem foco"

    def is_focused(self):
        return self.blocked_reason() is None

    def selected(self):
        return {"hwnd": 200, "pid": 20, "process_created": "123", "exe": "Trove.exe", "title": "Trove"}

    def maintain(self):
        pass

    def release_all(self):
        pass

    def suspend(self, value):
        pass

    def skill_region(self, skill):
        return skill.get("region")

    def skill_blocked_reason(self, skill):
        return None

    def client_region(self, require_focus=False):
        return (0, 0, 1920, 1080)

    def bind_region(self, region):
        return {"relative": list(region), "client_size": [1920, 1080]}
