"""Skill: Induktor wechseln (ZUKÜNFTIG — dokumentierter Stub).

Ausbaustufe 2. Der Induktor sitzt in einer Führung und ist mit **2 Schrauben**
befestigt. Ein 1-Zylinder-Pneumatikgreifer kann keine Schrauben lösen — dieser
Skill setzt deshalb einen **anderen Endeffektor** voraus (z. B. einen Akku-/
Pneumatik-Schrauber, hier ``ScrewdriverEndEffector`` genannt) und damit einen
**Werkzeugwechsel** (Tool-Changer, vgl. source_plan.md / "ATI QC").

Genau dafür existiert die Endeffektor-Abstraktion: der Skill modelliert hier den
Tool-Change-Schritt als dokumentierten Stub, ohne Implementierung. Er ist
absichtlich noch nicht im Orchestrator verdrahtet.
"""

from __future__ import annotations

from ..util.logging import get_logger
from .base import SkillInterface

_log = get_logger(__name__)


class ChangeInductorSkill(SkillInterface):
    """Wechselt den Induktor (2 Schrauben) — Zukunfts-Stub.

    Voraussetzungen (noch nicht erfüllt im ersten Ausbau):
        * Werkzeugwechsel auf ``ScrewdriverEndEffector`` (Tool-Changer).
        * Angelernte Posen für Schraubpunkte + Induktor-Greifpose.
        * SPS-/Sicherheitsfreigabe für Werkzeugwechsel.
    """

    name = "change_inductor"

    def precondition(self) -> bool:
        _log.info("change_inductor.precondition: Stub -> False (Ausbaustufe 2)")
        return False

    def execute(self) -> bool:
        # Skizze des späteren Ablaufs (alles Stub):
        #   1. Tool-Change: Greifer ablegen, Schrauber aufnehmen (ScrewdriverEndEffector).
        #   2. Zu Schraube 1 fahren -> lösen; zu Schraube 2 fahren -> lösen.
        #   3. Induktor aus Führung ziehen -> ablegen.
        #   4. Neuen Induktor einsetzen -> 2 Schrauben anziehen.
        #   5. Tool-Change zurück auf Greifer.
        raise NotImplementedError("change_inductor: Ausbaustufe 2 — erfordert ScrewdriverEndEffector + Tool-Changer")

    def recover(self) -> None:
        _log.warning("change_inductor.recover: Stub")
