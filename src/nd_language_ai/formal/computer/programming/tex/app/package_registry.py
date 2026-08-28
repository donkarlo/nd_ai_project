import re
from balanced_latex_reader import BalancedLatexReader


class PackageRegistry:
    def __init__(self, balanced_reader: BalancedLatexReader) -> None:
        self.balanced_reader = balanced_reader
        self.package_order = []
        self.package_options = {}

    def collect(self, preamble: str) -> None:
        masked_preamble = self.balanced_reader.mask_comments(preamble)
        self.collect_package_commands(masked_preamble)
        self.collect_pass_option_commands(masked_preamble)

    def collect_package_commands(self, masked_preamble: str) -> None:
        pattern = re.compile(r"\\(?:usepackage|RequirePackage)\s*")
        for match in pattern.finditer(masked_preamble):
            index = self.balanced_reader.skip_whitespace(masked_preamble, match.end())
            options = []
            if index < len(masked_preamble) and masked_preamble[index] == "[":
                try:
                    option_text, index = self.balanced_reader.read_group(masked_preamble, index, "[", "]")
                except ValueError:
                    continue
                options = self.split_values(option_text)
                index = self.balanced_reader.skip_whitespace(masked_preamble, index)
            if index >= len(masked_preamble) or masked_preamble[index] != "{":
                continue
            try:
                package_text, end_index = self.balanced_reader.read_group(masked_preamble, index, "{", "}")
            except ValueError:
                continue
            if end_index <= index:
                continue
            self.register_packages(self.split_values(package_text), options)

    def collect_pass_option_commands(self, masked_preamble: str) -> None:
        pattern = re.compile(r"\\PassOptionsToPackage\s*")
        for match in pattern.finditer(masked_preamble):
            index = self.balanced_reader.skip_whitespace(masked_preamble, match.end())
            if index >= len(masked_preamble) or masked_preamble[index] != "{":
                continue
            try:
                option_text, index = self.balanced_reader.read_group(masked_preamble, index, "{", "}")
            except ValueError:
                continue
            index = self.balanced_reader.skip_whitespace(masked_preamble, index)
            if index >= len(masked_preamble) or masked_preamble[index] != "{":
                continue
            try:
                package_text, end_index = self.balanced_reader.read_group(masked_preamble, index, "{", "}")
            except ValueError:
                continue
            if end_index <= index:
                continue
            self.register_packages(self.split_values(package_text), self.split_values(option_text))

    def register_packages(self, package_names: list[str], options: list[str]) -> None:
        for package_name in package_names:
            if not self.is_valid_package_name(package_name):
                continue
            if package_name not in self.package_options:
                self.package_order.append(package_name)
                self.package_options[package_name] = []
            for option in options:
                if option not in self.package_options[package_name]:
                    self.package_options[package_name].append(option)

    def ensure_package(self, package_name: str, options: tuple[str, ...] = ()) -> None:
        self.register_packages([package_name], list(options))

    def contains(self, package_name: str) -> bool:
        return package_name in self.package_options

    def split_values(self, text: str) -> list[str]:
        values = []
        for value in text.split(","):
            normalized_value = value.strip()
            if normalized_value:
                values.append(normalized_value)
        return values

    def is_valid_package_name(self, package_name: str) -> bool:
        return re.fullmatch(r"[A-Za-z0-9_.\-/]+", package_name) is not None

    def render(self) -> str:
        rendered_lines = []
        for package_name in self.reorder_packages():
            options = self.package_options[package_name]
            option_text = ""
            if options:
                option_text = "[" + ",".join(options) + "]"
            rendered_lines.append(f"\\usepackage{option_text}{{{package_name}}}")
        return "\n".join(rendered_lines)

    def reorder_packages(self) -> list[str]:
        late_packages = ("hyperref", "bookmark", "cleveref")
        regular_packages = [package_name for package_name in self.package_order if package_name not in late_packages]
        for package_name in late_packages:
            if package_name in self.package_order:
                regular_packages.append(package_name)
        return regular_packages
