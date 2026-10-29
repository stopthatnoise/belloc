"""Агульнае для правак Unity-бандлаў праз UnityPy.

Перад правай бандла Addressables трэба праверыць CRC у catalog.bin: калі ён не 0,
гульня змены адкіне. .orig і .bel — у install/target.py.
"""
from __future__ import annotations

import os

import UnityPy


def monobehaviours(env_or_path):
    """(obj, typetree) для кожнага MonoBehaviour, які чытаецца."""
    env = UnityPy.load(env_or_path) if isinstance(env_or_path, str) else env_or_path
    for o in env.objects:
        if o.type.name == "MonoBehaviour":
            try:
                yield o, o.read_typetree()
            except Exception:
                pass


def save(env, path: str):
    with open(path, "wb") as f:
        f.write(env.file.save(packer="lz4"))


def unity_version(game_data_dir: str) -> str | None:
    p = os.path.join(game_data_dir, "globalgamemanagers")
    if not os.path.exists(p):
        return None
    env = UnityPy.load(p)
    return next(iter(env.files.values())).unity_version
