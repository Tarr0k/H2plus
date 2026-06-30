"""h2_loader — Maschinenlader-Gerüst für den Unitree H2 PLUS.

Schichtenmodell (von oben nach unten):

    app -> core (Ablaufsteuerung) -> skills -> {motion, hal, perception, plc}

Höhere Schichten kennen ausschließlich die abstrakten Interfaces der tieferen
Schichten, nie deren konkrete Treiber. Dadurch sind Motion-Backend
(teach_replay heute, MoveIt2 später) und Endeffektor (Pneumatikgreifer heute,
Mehrfingerhand später) austauschbar, ohne dass Skill-Code geändert werden muss.

Dieser Stand ist bewusst Gerüst + Stubs — es findet keine echte Roboterbewegung
statt. Ausführung/Tests final auf dem Ubuntu-Zielsystem.
"""

__version__ = "0.5.1"
