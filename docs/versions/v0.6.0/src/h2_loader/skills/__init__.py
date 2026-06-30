"""Anwendungs-Skills (Laden/Entladen/Induktorwechsel).

Skills sind die fachliche Schicht. Sie orchestrieren Bewegung, Endeffektor und
SPS-Handshake — ausschließlich über Fassaden/Interfaces (``MotionPlannerInterface``,
``MachineIo`` (UDT-Schritt-Ebene), ``LocomotionInterface``, ``EndEffectorInterface`` via HAL).
Kein Skill importiert einen konkreten Treiber; dadurch bleiben Motion-Backend, Locomotion und
Endeffektor austauschbar. (Das flache ``Signal``/``PlcInterface`` ist Legacy, von Skills ungenutzt.)
"""
