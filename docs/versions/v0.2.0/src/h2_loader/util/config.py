"""YAML-Konfiguration laden und in typisierte Objekte überführen.

Grundsatz des Projekts: *Konfiguration statt Code*. Posen, Maschinengeometrie
und SPS-Signale liegen in ``config/*.yaml`` und werden hier in Dataclasses
geladen, damit der restliche Code mit Attributzugriff statt rohen Dicts
arbeitet. Die Dataclasses sind absichtlich tolerant (unbekannte Schlüssel
landen in ``extra``), damit das Schema wachsen kann, ohne Loader-Code zu brechen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Lädt eine YAML-Datei und liefert ihren Inhalt als Dict.

    Raises:
        FileNotFoundError: wenn die Datei nicht existiert.
        ValueError: wenn die Datei kein Mapping (Dict) auf oberster Ebene ist.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Erwartet ein YAML-Mapping in {p}, erhielt {type(data).__name__}")
    return data


@dataclass
class RobotConfig:
    """Roboter-/Treiberkonfiguration aus ``config/robot.yaml``.

    Attributes:
        driver: Treiberwahl, "sim" (MuJoCo) oder "sdk" (echte HW via unitree_sdk2_python).
        arms: Mapping Armseite ("left"/"right") -> Armparameter (z. B. Gelenkgrenzen).
        extra: alle übrigen, (noch) nicht typisierten Schlüssel.
    """

    driver: str = "sim"
    arms: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RobotConfig":
        known = {"driver", "arms"}
        return cls(
            driver=data.get("driver", "sim"),
            arms=data.get("arms", {}),
            extra={k: v for k, v in data.items() if k not in known},
        )

    @classmethod
    def load(cls, path: str | Path) -> "RobotConfig":
        return cls.from_dict(load_yaml(path))


@dataclass
class PlcConfig:
    """SPS-Konfiguration aus ``config/plc.yaml``."""

    endpoint: str = ""
    signals: dict[str, Any] = field(default_factory=dict)
    udt: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlcConfig":
        known = {"endpoint", "signals", "udt"}
        return cls(
            endpoint=data.get("endpoint", ""),
            signals=data.get("signals", {}),
            udt=data.get("udt", {}),
            extra={k: v for k, v in data.items() if k not in known},
        )

    @classmethod
    def load(cls, path: str | Path) -> "PlcConfig":
        return cls.from_dict(load_yaml(path))


@dataclass
class Pose:
    """Eine angelernte Pose: Gelenkwinkel je Arm.

    Attributes:
        name: sprechender Name der Pose (Dateiname/Skill-Bezug).
        joints: Mapping Armseite -> Liste von 7 Gelenkwinkeln [rad].
    """

    name: str
    joints: dict[str, list[float]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "Pose":
        data = load_yaml(path)
        return cls(name=data.get("name", Path(path).stem), joints=data.get("joints", {}))
