from pathlib import Path
import ast

path = Path('core/auth.py')
source = path.read_text()
tree = ast.parse(source, filename=str(path))
imported_from_ui = set()
for node in tree.body:
    if isinstance(node, ast.ImportFrom) and node.module == 'core.ui':
        imported_from_ui.update(alias.asname or alias.name for alias in node.names)
required = {'logo_data_uri', 'render_public_brand', 'safe'}
missing = sorted(required - imported_from_ui)
if missing:
    raise SystemExit('Missing core.ui login imports: ' + ', '.join(missing))
if 'def render_login()' not in source or 'logo_data_uri()' not in source or 'safe(settings.version)' not in source:
    raise SystemExit('Login render contract is incomplete')
print('Login import contract OK:', ', '.join(sorted(required)))
