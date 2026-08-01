from pathlib import Path
from dependency_resolver import DependencyResolver
from latex_document_parser import LatexDocumentParser
from parsed_document import ParsedDocument
from project_file_system import ProjectFileSystem
from source_file import SourceFile
from unresolved_reference import UnresolvedReference


class DependencyGraphBuilder:
    def __init__(self, source_directory: Path, project_file_system: ProjectFileSystem, parser: LatexDocumentParser, resolver: DependencyResolver) -> None:
        self.source_directory = source_directory
        self.project_file_system = project_file_system
        self.parser = parser
        self.resolver = resolver
        self.parsed_documents = {}
        self.unresolved_references = []
        self.resolved_dependency_count = 0

    def build_order(self, discovered_source_files: list[SourceFile]) -> tuple[list[ParsedDocument], list[UnresolvedReference], int]:
        discovered_by_path = {source_file.path.resolve(): source_file for source_file in discovered_source_files}
        entry_source_files = self.select_entry_source_files(discovered_source_files)
        ordered_documents = []
        visited_paths = set()
        active_paths = set()
        for source_file in entry_source_files:
            self.visit(source_file.path, discovered_by_path, ordered_documents, visited_paths, active_paths)
        for source_file in discovered_source_files:
            self.visit(source_file.path, discovered_by_path, ordered_documents, visited_paths, active_paths)
        return ordered_documents, self.unresolved_references, self.resolved_dependency_count

    def select_entry_source_files(self, source_files: list[SourceFile]) -> list[SourceFile]:
        root_files = [source_file for source_file in source_files if Path(source_file.relative_path).parent == Path(".")]
        if not root_files:
            return source_files[:1]
        scored_files = []
        source_directory_name = self.source_directory.name.casefold()
        project_name = self.source_directory.parent.name.casefold()
        for source_file in root_files:
            parsed_document = self.parse_source_file(source_file)
            dependency_count = len(parsed_document.body_dependencies) + len(parsed_document.preamble_dependencies)
            name_score = 0
            if source_file.path.stem.casefold() in {source_directory_name, project_name, project_name.removesuffix("_project")}:
                name_score = 1000
            if parsed_document.is_full_document:
                full_document_score = 100
            else:
                full_document_score = 0
            scored_files.append((name_score + full_document_score + dependency_count, source_file))
        scored_files.sort(key=lambda item: (-item[0], item[1].relative_path.casefold()))
        return [item[1] for item in scored_files]

    def visit(self, path: Path, discovered_by_path: dict[Path, SourceFile], ordered_documents: list[ParsedDocument], visited_paths: set[Path], active_paths: set[Path]) -> None:
        resolved_path = path.resolve()
        if resolved_path in visited_paths or resolved_path in active_paths:
            return
        active_paths.add(resolved_path)
        source_file = discovered_by_path.get(resolved_path)
        if source_file is None:
            relative_path = self.relative_path_for_external_file(resolved_path)
            source_file = SourceFile(resolved_path, relative_path, self.project_file_system.read_text(resolved_path))
        parsed_document = self.parse_source_file(source_file)
        for reference in parsed_document.preamble_dependencies:
            dependency_path = self.resolver.resolve(reference, resolved_path)
            if dependency_path is None:
                self.unresolved_references.append(UnresolvedReference(reference, source_file.relative_path, "preamble input"))
            else:
                self.resolved_dependency_count += 1
                self.visit(dependency_path, discovered_by_path, ordered_documents, visited_paths, active_paths)
        ordered_documents.append(parsed_document)
        for reference in parsed_document.body_dependencies:
            dependency_path = self.resolver.resolve(reference, resolved_path)
            if dependency_path is None:
                self.unresolved_references.append(UnresolvedReference(reference, source_file.relative_path, "body input"))
            else:
                self.resolved_dependency_count += 1
                self.visit(dependency_path, discovered_by_path, ordered_documents, visited_paths, active_paths)
        active_paths.remove(resolved_path)
        visited_paths.add(resolved_path)

    def parse_source_file(self, source_file: SourceFile) -> ParsedDocument:
        resolved_path = source_file.path.resolve()
        if resolved_path not in self.parsed_documents:
            self.parsed_documents[resolved_path] = self.parser.parse(source_file)
        return self.parsed_documents[resolved_path]

    def relative_path_for_external_file(self, path: Path) -> str:
        try:
            return path.relative_to(self.source_directory).as_posix()
        except ValueError:
            return path.as_posix()
