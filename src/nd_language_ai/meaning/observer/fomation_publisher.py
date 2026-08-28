from typing import List

from nd_robotic_ai.robot.robot import Meaning
from nd_robotic_ai.robot.robot import FormationSubscriber


class FormationPublisher:
    _meaning_formation_subscribers: List[FormationSubscriber]
    def attach_meaning_formation_subscriber(self, formation_subscriber:FormationSubscriber)->None: ...
    def detach_meaning_formation_subscriber(self, formation_subscriber: FormationSubscriber)->None: ...
    def notify_meaning_formation_subscribers(self, meaning:Meaning)->None: ...