from nd_robotic_ai.robot.robot import Morpheme
from typing import List

class Word(Meaning):
    """
    unhappiness
    unhappiness = Word(
        "unhappiness",
        morphemes=[
            Morpheme("un", [Syllable("un")]),
            Morpheme("happy", [Syllable("hap"), Syllable("py")]),
            Morpheme("ness", [Syllable("ness")])
        ]
    )
    """
    def __init__(self, morphemes:List[Morpheme]):
        self._morphemes = morphemes

    def get_morphemes(self) -> List[Morpheme]:
        return self._morphemes