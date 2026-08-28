from utilix.ui.cli.cli import Cli as CliBase
from sociomind.experiment.cli import Cli as SociomindExperimentCli

class Cli(CliBase):
    def run(self)-> None:
        if self._args[0] == "xpr":
            xpr_cli = SociomindExperimentCli(self.get_program_args())
            xpr_cli.run()