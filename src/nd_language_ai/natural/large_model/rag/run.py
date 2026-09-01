import sys
from pathlib import Path


source_root = Path(__file__).resolve().parents[4]
source_root_text = str(source_root)
if source_root_text not in sys.path:
    sys.path.insert(0, source_root_text)

from nd_language_ai.natural.large_model.rag.application import RagApplication


def main() -> int:
    return RagApplication().run()


if __name__ == "__main__":
    raise SystemExit(main())
