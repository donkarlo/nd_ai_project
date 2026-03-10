from nd_utility.data.kind.dic.dic import Dic


class Duration:
    def __init__(self):
        self._existing_morphems = {}
        self._existing_morphems["minute"] = {"30m", "30 m", "30 minute", "30 minutes"}

        self._existing_morphems_dic = Dic({self._existing_morphems})