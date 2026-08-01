from asset_resolver import AssetResolver
from balanced_latex_reader import BalancedLatexReader
from body_sanitizer import BodySanitizer
from dependency_graph_builder import DependencyGraphBuilder
from dependency_resolver import DependencyResolver
from folder_heading_builder import FolderHeadingBuilder
from heading_transformer import HeadingTransformer
from interactive_cli import InteractiveCli
from latex_document_parser import LatexDocumentParser
from latex_output_validator import LatexOutputValidator
from latex_project_merger import LatexProjectMerger
from output_writer import OutputWriter
from package_registry import PackageRegistry
from preamble_collector import PreambleCollector
from project_file_system import ProjectFileSystem


class LatexMergerApplication:
    def run(self) -> int:
        interactive_cli = InteractiveCli()
        configuration = interactive_cli.ask_configuration()
        project_file_system = ProjectFileSystem()
        balanced_reader = BalancedLatexReader()
        parser = LatexDocumentParser(balanced_reader)
        discovered_source_files = project_file_system.discover_tex_files(configuration.source_directory)
        dependency_resolver = DependencyResolver(configuration.source_directory, project_file_system)
        graph_builder = DependencyGraphBuilder(configuration.source_directory, project_file_system, parser, dependency_resolver)
        ordered_documents, unresolved_references, resolved_dependency_count = graph_builder.build_order(discovered_source_files)
        package_registry = PackageRegistry(balanced_reader)
        preamble_collector = PreambleCollector(balanced_reader, package_registry)
        heading_transformer = HeadingTransformer(balanced_reader, configuration.starting_heading, configuration.document_class)
        folder_heading_builder = FolderHeadingBuilder(configuration.source_directory, heading_transformer)
        body_sanitizer = BodySanitizer(balanced_reader)
        asset_resolver = AssetResolver(configuration.source_directory, balanced_reader)
        project_merger = LatexProjectMerger(configuration, preamble_collector, heading_transformer, folder_heading_builder, body_sanitizer, asset_resolver)
        tex_content, warnings = project_merger.merge(ordered_documents)
        output_validator = LatexOutputValidator(balanced_reader, configuration.bibliography_path.as_posix())
        output_validator.validate(tex_content)
        output_writer = OutputWriter(project_file_system)
        output_writer.write(configuration.output_tex_path, tex_content)
        warning_count = len(warnings) + len(unresolved_references)
        interactive_cli.print_result(configuration.output_tex_path, len(ordered_documents), resolved_dependency_count, warning_count)
        return 0
