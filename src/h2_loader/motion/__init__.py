"""Bewegungs-Backend hinter ``MotionPlannerInterface``.

Dies ist der ROS2-Umstiegspunkt: Skills rufen nur das Interface. Heute steckt
``teach_replay`` dahinter (angelernte Posen abfahren), später ``moveit2_backend``
(ROS2/MoveIt2). Ein Backend-Wechsel ändert keinen Skill.
"""
