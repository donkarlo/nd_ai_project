from nd_robotic_ai.robot.robot import Meaning


class Language:
    """
    For a language first the words are determined then with some methods the necessary alphabets for those words are determined
    - Language is how we talk about an ontology
    - Language must be both useful for surviaval for example it must increase homeostasis value but it also should turn so much deceptive that it reverses back its change_direction to reduce and even exinct the robot or race.
    - In fact a powerful language should be more enable to create so much illusion that it reduces the homeostasis value more.
    - Language can not exist anywhere other_kind than an agent (Robot mind)
    - Language is internalized through repeated social interaction
    """

    def __init__(self, meanings:List[Meaning]):
        self._meanings = meanings

    def get_illusion_rate(self) -> float:
        """
        rates of illusion is
        -dream
        -art
        -religion
        -suiacide for a belief
        Returns:

        """
        pass

    def get_pragmatism_rate(self) -> float:
        pass

    def get_meanings(self):
        return self._meanings

    def get_meaning_expansion_potential_rate(self)->float:
        """According to current self._meannings"""
        pass

