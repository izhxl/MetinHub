import ast
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
import json
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import manutenzione_metin as maintenance
spec = importlib.util.spec_from_file_location('release_tool', ROOT / 'tools/crea_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class DistributionTests(unittest.TestCase):
    def test_version(self):
        version = (ROOT / 'VERSION.txt').read_text().strip()
        self.assertEqual(len(maintenance.versione(version)), 3)
        self.assertIn("'VERSION.txt'", (ROOT / 'osserva_metin.py').read_text())

    def test_release_is_accepted_by_updater(self):
        with tempfile.TemporaryDirectory() as t:
            archive = release.build(Path(t) / 'dist', 'https://example.com/MetinHub.zip')
            names = maintenance.estrai_pacchetto(archive, Path(t) / 'extracted')
            self.assertIn('VERSION.txt', names)
            self.assertIn('Installa_MetinHub.ps1', names)
            self.assertNotIn('metinhub_settings.json', names)
            manifest = json.loads((Path(t) / 'dist/latest.json').read_text())
            import hashlib
            self.assertEqual(manifest['sha256'], hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertEqual(manifest['product'], 'MetinHub')

    def test_reject_unsafe_packages(self):
        for extra in ('MetinHub/../bad.py', 'Other/tool.py',
                      'MetinHub/metinhub_settings.json', 'MetinHub/metinhub_log.txt'):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as t:
                archive = Path(t) / 'bad.zip'
                with zipfile.ZipFile(archive, 'w') as z:
                    z.writestr(extra, 'bad')
                with self.assertRaises(ValueError):
                    maintenance.estrai_pacchetto(archive, Path(t) / 'out')

    def test_python_syntax(self):
        for path in ROOT.rglob('*.py'):
            if not any(part.startswith('.') for part in path.relative_to(ROOT).parts):
                with self.subTest(path=path.name):
                    compile(path.read_text(encoding='utf-8-sig'), str(path), 'exec')

    def test_installer_assets_exist(self):
        for name in ('MetinHub.ico', 'MetinHub.png', 'MetinHub.manifest',
                     'MetinHub_Launcher.cs', 'VERSION.txt', 'Installa_MetinHub.ps1',
                     'Disinstalla_MetinHub.ps1', 'Avvia_MetinHub.bat'):
            self.assertTrue((ROOT / name).is_file(), name)
        text = (ROOT / 'Installa_MetinHub.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('$manifestText=@"', text)  # version must interpolate
        self.assertNotIn('0.14.1', text)


class ThemeRegressionTests(unittest.TestCase):
    def test_no_shadowed_tk_methods(self):
        import tkinter as tk
        tree = ast.parse((ROOT / 'tema_metin.py').read_text())
        for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            if cls.name.startswith('Anteprima'):
                for node in ast.walk(cls):
                    if (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store)
                            and isinstance(node.value, ast.Name) and node.value.id == 'self'):
                        self.assertFalse(callable(getattr(tk.Canvas, node.attr, None)), node.attr)

    def test_preview_native_widget_lookup(self):
        import tkinter as tk
        import tema_metin as theme
        root = tk.Tcl()
        def initialize(widget, parent, **kw):
            widget.master = parent
            widget.tk = parent.tk
            widget.children = {}
            widget._w = '.preview'
        with patch.object(tk.Canvas, '__init__', initialize), \
             patch.object(tk.Canvas, 'bind', return_value='binding'), \
             patch.object(tk.Canvas, 'winfo_toplevel', return_value=root), \
             patch.object(root, 'bind', return_value='binding'), \
             patch.object(theme.AnteprimaTerreno, '_schedule'):
            for cls in (theme.AnteprimaSchegge, theme.AnteprimaPesca):
                widget = cls(root)
                self.assertIs(widget._root(), root)
                self.assertIs(widget.nametowidget('.'), root)

    def test_control_panel_cap_and_narrow_layout(self):
        import tema_metin as theme
        from types import SimpleNamespace
        from unittest.mock import Mock
        columns = {}
        def column(index, **kw):
            columns.setdefault(index, {}).update(kw)
        frame = SimpleNamespace(_wide=None, threshold=840, _control_limit=480,
                                columnconfigure=column, sinistra=Mock(), destra=Mock())
        for width in (2000, 4000):
            theme.LayoutSchegge._layout(frame, SimpleNamespace(width=width))
            self.assertEqual(columns[1]['minsize'], 480)
            self.assertEqual(columns[1]['weight'], 0)
        theme.LayoutSchegge._layout(frame, SimpleNamespace(width=600))
        self.assertEqual(columns[1]['minsize'], 0)
        self.assertEqual(frame.destra.grid.call_args.kwargs['row'], 1)

    def test_resize_does_not_postpone_header_indefinitely(self):
        import tema_metin as theme
        from types import SimpleNamespace
        calls = []
        fake = SimpleNamespace(_header_job=None, _header=lambda: None,
                               after=lambda ms, fn: calls.append((ms, fn)) or 'job')
        for _ in range(100):
            theme.Navigazione._schedule_header(fake)
        self.assertEqual(len(calls), 1)
        self.assertLessEqual(calls[0][0], 40)


if __name__ == '__main__':
    unittest.main()
