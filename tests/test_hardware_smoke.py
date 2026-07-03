"""Hardware-Smoke-Test — läuft NUR auf dem Zielsystem mit echtem SDK und Roboter.

Übersprungen, wenn:
  - ``unitree_sdk2py`` nicht installiert ist (z. B. dieser Windows-Entwicklungsrechner), ODER
  - die Umgebungsvariable ``H2_HARDWARE`` nicht auf ``"1"`` gesetzt ist.

Damit bleibt dieser Test in der Default-Suite immer SKIPPED und erfordert
explizites Opt-in am Zielsystem (``H2_HARDWARE=1 pytest tests/test_hardware_smoke.py``).
"""

from __future__ import annotations

import os

import pytest

unitree_sdk2py = pytest.importorskip("unitree_sdk2py", exc_type=ImportError)

if os.environ.get("H2_HARDWARE") != "1":
    pytest.skip(
        "Hardware-Smoke-Test übersprungen — nur mit H2_HARDWARE=1 auf dem Zielsystem ausführen",
        allow_module_level=True,
    )


def test_channel_factory_initialize_importierbar() -> None:
    """Platzhalter-Smoke: ChannelFactoryInitialize ist aus dem echten SDK importierbar."""
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize

    assert callable(ChannelFactoryInitialize)
