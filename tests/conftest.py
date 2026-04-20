import sys
import os
import importlib.util
import importlib.machinery
import types

src_path = os.path.join(os.path.dirname(__file__), '..', 'src')
sys.path.insert(0, src_path)

# Pre-load all io serializer modules to work around built-in io module conflict
io_path = os.path.join(src_path, 'io')
serializers_path = os.path.join(io_path, 'serializers')

def load_serializer_module(name, filename):
    """Load a serializer module with relative imports fixed."""
    spec = importlib.util.spec_from_file_location(
        f'io_serializers_{name}',
        os.path.join(serializers_path, filename)
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[f'io_serializers_{name}'] = module
    spec.loader.exec_module(module)
    return module

# Load base.py
io_serializers_base = load_serializer_module('base', 'base.py')

# Load json_serializer.py with fixed imports
json_code = open(os.path.join(serializers_path, 'json_serializer.py')).read()
json_code = json_code.replace('from .base import BaseSerializer',
                               'from io_serializers_base import BaseSerializer')
io_serializers_json = types.ModuleType('io_serializers_json_serializer')
io_serializers_json.__file__ = os.path.join(serializers_path, 'json_serializer.py')
sys.modules['io_serializers_json_serializer'] = io_serializers_json
exec(compile(json_code, os.path.join(serializers_path, 'json_serializer.py'), 'exec'),
     io_serializers_json.__dict__)

# Load yaml_serializer.py with fixed imports
yaml_code = open(os.path.join(serializers_path, 'yaml_serializer.py')).read()
yaml_code = yaml_code.replace('from .base import BaseSerializer',
                               'from io_serializers_base import BaseSerializer')
io_serializers_yaml = types.ModuleType('io_serializers_yaml_serializer')
io_serializers_yaml.__file__ = os.path.join(serializers_path, 'yaml_serializer.py')
sys.modules['io_serializers_yaml_serializer'] = io_serializers_yaml
exec(compile(yaml_code, os.path.join(serializers_path, 'yaml_serializer.py'), 'exec'),
     io_serializers_yaml.__dict__)

# Load csv_serializer.py with fixed imports
csv_code = open(os.path.join(serializers_path, 'csv_serializer.py')).read()
csv_code = csv_code.replace('from .base import BaseSerializer',
                             'from io_serializers_base import BaseSerializer')
io_serializers_csv = types.ModuleType('io_serializers_csv_serializer')
io_serializers_csv.__file__ = os.path.join(serializers_path, 'csv_serializer.py')
sys.modules['io_serializers_csv_serializer'] = io_serializers_csv
exec(compile(csv_code, os.path.join(serializers_path, 'csv_serializer.py'), 'exec'),
     io_serializers_csv.__dict__)

# Create io.serializers namespace
try:
    builtin_io = __import__('io')
    io_module = types.ModuleType('io')

    # Copy built-in io attributes
    for attr in dir(builtin_io):
        if not attr.startswith('_'):
            try:
                setattr(io_module, attr, getattr(builtin_io, attr))
            except (AttributeError, TypeError):
                pass

    # Add our custom serializers subpackage
    serializers_module = types.ModuleType('serializers')
    serializers_module.BaseSerializer = io_serializers_base.BaseSerializer
    serializers_module.JsonSerializer = io_serializers_json.JsonSerializer
    serializers_module.YamlSerializer = io_serializers_yaml.YamlSerializer
    serializers_module.CsvSerializer = io_serializers_csv.CsvSerializer

    io_module.serializers = serializers_module
    sys.modules['io'] = io_module
    sys.modules['io.serializers'] = serializers_module
    sys.modules['io.serializers.base'] = io_serializers_base
    sys.modules['io.serializers.json_serializer'] = io_serializers_json
    sys.modules['io.serializers.yaml_serializer'] = io_serializers_yaml
    sys.modules['io.serializers.csv_serializer'] = io_serializers_csv
except Exception as e:
    print(f"Warning: Could not set up io.serializers: {e}")
    import traceback
    traceback.print_exc()