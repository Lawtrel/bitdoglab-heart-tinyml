import ast
from pathlib import Path
import unittest
import heart_tinyml

class ArchitectureTests(unittest.TestCase):
    def test_domain_and_use_cases_do_not_import_concrete_adapters(self):
        root = Path(heart_tinyml.__file__).parent
        forbidden = ("ai_edge_litert", "serial", "http", "heart_tinyml.adapters", "heart_tinyml.web")
        for layer in ("domain", "application"):
            for file in (root / layer).glob("*.py"):
                tree = ast.parse(file.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        modules = [entry.name for entry in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        modules = [node.module or ""]
                        self.assertNotIn(node.module, ("adapters", "web"))
                    else:
                        continue
                    for module in modules:
                        self.assertFalse(module.startswith(forbidden), (file, module))
