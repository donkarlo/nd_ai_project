from pathlib import Path
from document_class_option import DocumentClassOption
from heading_option import HeadingOption
from merge_configuration import MergeConfiguration


class InteractiveCli:
    def __init__(self) -> None:
        self.bibliography_path = Path("/home/donkarlo/Dropbox/repo/nd_shared_research/bibliography/bibliography.bib")
        self.document_class_options = (
            DocumentClassOption("article", "documents without chapters", False),
            DocumentClassOption("report", "reports and theses with chapters", True),
            DocumentClassOption("book", "books with chapters and parts", True),
            DocumentClassOption("scrartcl", "KOMA-Script article", False),
            DocumentClassOption("scrreprt", "KOMA-Script report", True),
            DocumentClassOption("scrbook", "KOMA-Script book", True),
        )

    def ask_configuration(self) -> MergeConfiguration:
        source_directory = self.ask_source_directory()
        document_class_option = self.ask_document_class()
        starting_heading = self.ask_starting_heading(document_class_option)
        output_tex_path = source_directory / "merged_project.tex"
        return MergeConfiguration(source_directory, document_class_option.key, starting_heading.command, output_tex_path, self.bibliography_path)

    def ask_source_directory(self) -> Path:
        while True:
            raw_path = input("Source directory path: ").strip().strip('"').strip("'")
            source_directory = Path(raw_path).expanduser().resolve()
            if source_directory.is_dir():
                return source_directory
            print("The directory does not exist. Enter a valid directory path.")

    def ask_document_class(self) -> DocumentClassOption:
        print("\nSelect the output document class:")
        for index, option in enumerate(self.document_class_options, start=1):
            default_marker = ""
            if option.key == "book":
                default_marker = " [default]"
            print(f"  {index}. {option.key} - {option.description}{default_marker}")
        selected_index = self.ask_number(len(self.document_class_options), 3)
        return self.document_class_options[selected_index - 1]

    def ask_starting_heading(self, document_class_option: DocumentClassOption) -> HeadingOption:
        options = self.create_heading_options(document_class_option)
        default_index = 1
        if document_class_option.supports_chapter:
            default_index = 2
        print(f"\nSelect the starting heading for document class '{document_class_option.key}':")
        for index, option in enumerate(options, start=1):
            default_marker = ""
            if index == default_index:
                default_marker = " [default]"
            print(f"  {index}. \\{option.command}{default_marker}")
        selected_index = self.ask_number(len(options), default_index)
        return options[selected_index - 1]

    def create_heading_options(self, document_class_option: DocumentClassOption) -> tuple[HeadingOption, ...]:
        options = [HeadingOption("part", "part")]
        if document_class_option.supports_chapter:
            options.append(HeadingOption("chapter", "chapter"))
        options.extend((
            HeadingOption("section", "section"),
            HeadingOption("subsection", "subsection"),
            HeadingOption("subsubsection", "subsubsection"),
            HeadingOption("paragraph", "paragraph"),
            HeadingOption("subparagraph", "subparagraph"),
        ))
        return tuple(options)

    def ask_number(self, maximum: int, default_value: int) -> int:
        while True:
            raw_value = input("Enter option number: ").strip()
            if raw_value == "":
                return default_value
            if raw_value.isdigit():
                selected_value = int(raw_value)
                if 1 <= selected_value <= maximum:
                    return selected_value
            print(f"Enter a number from 1 to {maximum}.")

    def print_result(self, tex_path: Path, processed_files: int, resolved_dependencies: int, warning_count: int) -> None:
        print(f"\nCreated: {tex_path}")
        print(f"Processed TeX files: {processed_files}")
        print(f"Resolved dependencies: {resolved_dependencies}")
        print(f"Warnings: {warning_count}")
