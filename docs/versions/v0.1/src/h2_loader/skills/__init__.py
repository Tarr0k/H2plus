"""Anwendungs-Skills (Laden/Entladen/Induktorwechsel).

Skills sind die fachliche Schicht. Sie orchestrieren Bewegung, Endeffektor und
SPS-Handshake — ausschließlich über Interfaces (``MotionPlannerInterface``,
``PlcInterface``, ``EndEffectorInterface`` via HAL). Kein Skill importiert einen
konkreten Treiber; dadurch bleibt Motion-Backend und Endeffektor austauschbar.
"""
