from utilix.oop.inheritance.overriding.override_from import override_from
from utilix.pythonx.project.project import Project


class Latex(Project):
    @override_from(Project)
    def run(self):
        pass