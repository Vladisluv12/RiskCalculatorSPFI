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

# Load excel_serializer.py with fixed imports
excel_code = open(os.path.join(serializers_path, 'excel_serializer.py')).read()
excel_code = excel_code.replace('from .base import BaseSerializer',
                                'from io_serializers_base import BaseSerializer')
io_serializers_excel = types.ModuleType('io_serializers_excel_serializer')
io_serializers_excel.__file__ = os.path.join(serializers_path, 'excel_serializer.py')
sys.modules['io_serializers_excel_serializer'] = io_serializers_excel
exec(compile(excel_code, os.path.join(serializers_path, 'excel_serializer.py'), 'exec'),
     io_serializers_excel.__dict__)

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
    serializers_module.ExcelSerializer = io_serializers_excel.ExcelSerializer

    io_module.serializers = serializers_module
    sys.modules['io'] = io_module
    sys.modules['io.serializers'] = serializers_module
    sys.modules['io.serializers.base'] = io_serializers_base
    sys.modules['io.serializers.json_serializer'] = io_serializers_json
    sys.modules['io.serializers.yaml_serializer'] = io_serializers_yaml
    sys.modules['io.serializers.csv_serializer'] = io_serializers_csv
    sys.modules['io.serializers.excel_serializer'] = io_serializers_excel

    # Load portfolio_io.py (uses absolute imports that resolve via sys.modules)
    portfolio_code = open(os.path.join(io_path, 'portfolio_io.py')).read()
    io_portfolio = types.ModuleType('io_portfolio_io')
    io_portfolio.__file__ = os.path.join(io_path, 'portfolio_io.py')
    sys.modules['io_portfolio_io'] = io_portfolio
    exec(compile(portfolio_code, os.path.join(io_path, 'portfolio_io.py'), 'exec'),
         io_portfolio.__dict__)
    sys.modules['io.portfolio_io'] = io_portfolio
    io_module.portfolio_io = io_portfolio

    # Load results_exporter.py (uses absolute imports that resolve via sys.modules)
    results_code = open(os.path.join(io_path, 'results_exporter.py')).read()
    io_results = types.ModuleType('io_results_exporter')
    io_results.__file__ = os.path.join(io_path, 'results_exporter.py')
    sys.modules['io_results_exporter'] = io_results
    exec(compile(results_code, os.path.join(io_path, 'results_exporter.py'), 'exec'),
         io_results.__dict__)
    sys.modules['io.results_exporter'] = io_results
    io_module.results_exporter = io_results

    # Load report_builder.py (uses only stdlib and fpdf imports)
    report_code = open(os.path.join(io_path, 'report_builder.py')).read()
    io_report = types.ModuleType('io_report_builder')
    io_report.__file__ = os.path.join(io_path, 'report_builder.py')
    sys.modules['io_report_builder'] = io_report
    exec(compile(report_code, os.path.join(io_path, 'report_builder.py'), 'exec'),
         io_report.__dict__)
    sys.modules['io.report_builder'] = io_report
    io_module.report_builder = io_report
except Exception as e:
    print(f"Warning: Could not set up io.serializers: {e}")
    import traceback
    traceback.print_exc()