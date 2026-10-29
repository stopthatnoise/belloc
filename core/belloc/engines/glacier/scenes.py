"""Да якой місіі і сцэны належыць рэпліка (DLGE) — па графе спасылак рэсурсаў.

Карані — сцэны з packagedefinition.txt (`[assembly:/_knt/scenes/missions/<місія>/
segment_….brick].pc_entitytype`): іх хэшы — rpkg.path_hash. Ад усіх каранёў адначасова
ідзе пошук ушыркі ўніз па спасылках; кожны рэсурс атрымлівае БЛІЖЭЙШЫЯ сцэны (агульныя
рэсурсы далёка ад кожнай сцэны, таму не зліваюць усё). Рэпліка з адной сцэны — у
табліцы гэтай сцэны, з некалькіх сцэн адной місіі — `_shared` місіі, з розных місій —
агульная (`_common`). Парадак рэплік у сцэне — абыход у глыбіню ад сцэны ў парадку
спасылак: у кат-сцэнах і размовах дае парадак гульні (праверана на Clover 2026-10-27).

Місіі — "missions" у секцыі glacier: [[рэгулярка па шляху, назва], …] у храналагічным
парадку (храналогія — з JSON гульні KNT_Missions: «M01 - …» …).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import rpkg

MASK = 0x00FFFFFFFFFFFFFF


@dataclass
class Place:
    mission: str | None      # назва з "missions" або None (розныя місіі / агульнае)
    segment: str | None      # сцэна ў межах місіі або None (некалькі сцэн)
    order: int               # парадак рэплікі ў сцэне (абыход), інакш вялікі


def segment_name(path: str) -> str:
    """[assembly:/…/missions/dahlia/segment_dahlia_auction.brick].pc_entitytype → auction."""
    m = re.search(r"/([^/\]]+)\.(?:brick|entity)\]", path)
    name = m.group(1) if m else path
    folder = re.search(r"/(?:missions|locations)/([^/]+)/", path)
    name = re.sub(r"^(segment|chunk|level|global)_", "", name)
    if folder:
        name = re.sub(rf"^{re.escape(folder.group(1))}_?", "", name) or name
    return name


def places(arc: rpkg.Archive, pd_text: str, missions: list[list[str]]) -> dict[int, Place]:
    """{хэш DLGE: Place}."""
    low = arc.by_low56()
    paths = [l.strip() for l in pd_text.splitlines() if l.startswith("[")]
    roots = {}
    for p in paths:
        h = low.get(rpkg.path_hash(p))
        if h is not None and (".brick]" in p or ".entity]" in p):
            roots.setdefault(h, p)
    children: dict[int, list[int]] = {}
    for h, e in arc.entries.items():
        cs = [low[r & MASK] for r in e.ref_hashes() if (r & MASK) in low]
        if cs:
            children[h] = cs

    # бліжэйшыя карані: пошук ушыркі ад усіх адначасова
    near: dict[int, frozenset[int]] = {h: frozenset([h]) for h in roots}
    frontier = {h: {h} for h in roots}
    while frontier:
        nxt: dict[int, set[int]] = {}
        for h, s in frontier.items():
            for c in children.get(h, ()):
                if c not in near:
                    nxt.setdefault(c, set()).update(s)
        for c, s in nxt.items():
            near[c] = frozenset(s)
        frontier = nxt

    def mission_of(path: str) -> str | None:
        return next((name for pat, name in missions if re.search(pat, path)), None)

    dlge = {h for h, e in arc.entries.items() if e.typ == "DLGE"}
    # парадак у сцэне: абыход у глыбіню ў парадку спасылак (першае наведванне)
    order: dict[tuple[int, int], int] = {}
    for root in roots:
        seen, stack, i = {root}, [root], 0
        while stack:
            h = stack.pop()
            if h in dlge:
                order[(root, h)] = i
                i += 1
            for c in reversed(children.get(h, ())):
                if c not in seen:
                    seen.add(c)
                    stack.append(c)

    out = {}
    for h in dlge:
        rs = near.get(h, frozenset())
        ms = {mission_of(roots[r]) for r in rs}
        mission = ms.pop() if len(ms) == 1 else None
        seg, o = None, 1 << 30
        if mission and len(rs) == 1:
            r = next(iter(rs))
            seg, o = segment_name(roots[r]), order.get((r, h), o)
        out[h] = Place(mission, seg, o)
    return out
