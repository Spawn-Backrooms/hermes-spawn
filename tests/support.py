"""Import plugin submodules without executing registration or needing Hermes."""
import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "_hermes_spawn_test_plugin"
if PACKAGE not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        PACKAGE, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
    )
    module = types.ModuleType(PACKAGE)
    module.__spec__ = spec
    module.__path__ = list(spec.submodule_search_locations)
    module.__package__ = PACKAGE
    sys.modules[PACKAGE] = module


def load(name):
    fullname = PACKAGE + "." + name
    if fullname not in sys.modules:
        spec = importlib.util.spec_from_file_location(fullname, ROOT / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[fullname] = module
        spec.loader.exec_module(module)
    return sys.modules[fullname]
