"""Job-Dispatch-Ebene: empfängt SPS-Aufträge und führt den passenden Skill aus.

Verdrahtet den OPC-UA-Handshake mit dem Skill-Dispatch-Dict.  Für jeden Auftrag,
den ``poll_job()`` liefert, wird der registrierte Skill aufgerufen; das Ergebnis
wird als ``JobOutcome`` zurückgegeben.

Ablauf je ``step()``:
    1. Heartbeat ticken.
    2. Auf Auftrag warten (kein Auftrag → None).
    3. Safety-Gate prüfen.
    4. Auftrag akzeptieren, Skill suchen und ausführen.
    5. Ergebnis an die SPS melden.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.safety import SafetyGate
from ..plc.handshake import H2HandshakeClient
from ..plc.udt import JobRequest, JobResult
from ..skills.base import SkillInterface
from ..util.logging import get_logger

_log = get_logger(__name__)


@dataclass(frozen=True)
class JobOutcome:
    """Ergebnis eines einzelnen Job-Dispatch-Schritts.

    Attributes:
        job_id:    Job-ID aus dem SPS-Auftrag.
        request:   Auftragsart (LOAD, UNLOAD, …).
        result:    Ergebnis (OK, NOK, OPEN).
        skill_ran: True, wenn ein Skill tatsächlich ausgeführt wurde.
    """

    job_id: int
    request: JobRequest
    result: JobResult
    skill_ran: bool


class JobRunner:
    """Empfängt SPS-Aufträge über den Handshake und dispatcht sie an Skills.

    Args:
        handshake: H2-Handshake-Client (Stub oder echtes OPC-UA-Objekt).
        skills:    Mapping Auftragsart → Skill-Implementierung.
        safety:    Software-Freigabe-Gate (Standard: frisch erzeugtes SafetyGate).
    """

    def __init__(
        self,
        handshake: H2HandshakeClient,
        skills: dict[JobRequest, SkillInterface],
        safety: SafetyGate | None = None,
    ) -> None:
        self._handshake = handshake
        self._skills = skills
        self._safety = safety if safety is not None else SafetyGate()

    def step(self) -> JobOutcome | None:
        """Verarbeitet genau einen SPS-Auftrag (falls vorhanden).

        Returns:
            ``JobOutcome`` bei einem verarbeiteten Auftrag, ``None`` wenn kein
            neuer Auftrag vorliegt.
        """
        # 1. Heartbeat ticken
        self._handshake.tick_heartbeat()

        # 2. Auf neuen Auftrag prüfen
        job_tuple = self._handshake.poll_job()
        if job_tuple is None:
            return None

        job_req, job_id, part_type = job_tuple

        # 3. Safety-Gate prüfen — vor accept_job, damit die SPS nicht blockiert
        if not self._safety.is_clear():
            _log.error(
                "JobRunner: Safety nicht frei — Auftrag %s (jobId=%d) wird mit NOK abgeschlossen",
                job_req.name,
                job_id,
            )
            self._handshake.accept_job(job_id)
            self._handshake.finish_job(JobResult.NOK)
            return JobOutcome(job_id=job_id, request=job_req, result=JobResult.NOK, skill_ran=False)

        # 4. Auftrag akzeptieren
        self._handshake.accept_job(job_id)

        # Skill suchen
        skill = self._skills.get(job_req)
        if skill is None:
            _log.warning(
                "JobRunner: kein Skill für Auftragsart %s (jobId=%d) registriert",
                job_req.name,
                job_id,
            )
            self._handshake.finish_job(JobResult.NOK)
            return JobOutcome(job_id=job_id, request=job_req, result=JobResult.NOK, skill_ran=False)

        # 5. Skill ausführen
        self._handshake.set_robot_in_machine(True)
        result = JobResult.NOK
        try:
            ok = skill.precondition() and skill.execute()
            if not ok:
                skill.recover()
            else:
                result = JobResult.OK
        except Exception:
            _log.exception(
                "JobRunner: unerwartete Ausnahme in Skill '%s' (jobId=%d)", skill.name, job_id
            )
            skill.recover()
        finally:
            self._handshake.set_robot_in_machine(False)

        self._handshake.finish_job(result)
        return JobOutcome(job_id=job_id, request=job_req, result=result, skill_ran=True)

    def run_until_idle(self, max_steps: int = 16) -> list[JobOutcome]:
        """Verarbeitet Aufträge bis kein neuer mehr vorliegt (oder max_steps erreicht).

        Args:
            max_steps: Maximale Anzahl der Schritte; verhindert Endlosschleifen.

        Returns:
            Liste aller verarbeiteten ``JobOutcome``-Objekte (ohne None-Einträge).
        """
        outcomes: list[JobOutcome] = []
        for _ in range(max_steps):
            outcome = self.step()
            if outcome is None:
                break
            outcomes.append(outcome)
        return outcomes
