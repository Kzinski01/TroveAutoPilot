"""Repair malformed saved fields before any worker consumes configuration."""

import copy

import settings_validation as validation


def _repair(values, defaults, schema):
    for name, check in schema.items():
        try:
            values[name] = check(values[name])
        except (ValueError, TypeError, KeyError):
            values[name] = copy.deepcopy(defaults[name])


def _coordinates(value, length, positive_size=False):
    if not isinstance(value, list) or len(value) != length:
        return False
    if any(type(item) is not int or abs(item) > 100000 for item in value):
        return False
    return not positive_size or all(0 < item <= 32768 for item in value[-2:])


def _repair_region(values, name):
    if values.get(name) is not None and not _coordinates(values[name], 4, True):
        values[name] = None


def _repair_skill(skill, default):
    _repair(skill, default, {**validation.SKILL,
                            "ready_score": validation.number(0, 1),
                            "cooldown_score": validation.number(0, 1)})
    _repair_region(skill, "region")
    binding = skill.get("window_region")
    if binding is not None and not (
            isinstance(binding, dict)
            and _coordinates(binding.get("relative"), 4, True)
            and _coordinates(binding.get("client_size"), 2, True)):
        skill.pop("window_region", None)
        skill["region"] = None
        skill["ready_score"] = 0.0


def sanitize(cfg, defaults):
    _repair(cfg, defaults, {**validation.SETTINGS,
                           "input_mode": validation.choice("foreground", "messages"),
                           "scan_interval": validation.number(0.01, 60),
                           "dialog_interval": validation.number(0.05, 60)})
    for section, schema in validation.SECTIONS.items():
        _repair(cfg[section], defaults[section], schema)
    for skill, default in zip(cfg["skills"], defaults["skills"]):
        _repair_skill(skill, default)
    for name in ("claim", "invite"):
        _repair(cfg[name], defaults[name], validation.DIALOG)
        _repair_region(cfg[name], "template_region")
        if not _coordinates(cfg[name].get("click_offset"), 2):
            cfg[name]["click_offset"] = [0, 0]
    _repair(cfg["secondary"], defaults["secondary"],
            {"key": validation.key, "interval": validation.number(0.5, 86400)})
    return cfg
