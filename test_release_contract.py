import ast
import hashlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path

import app
from release_identity import release_identity


ROOT=Path(__file__).resolve().parent


class ReleaseContractTests(unittest.TestCase):
    def test_frozen_code_and_models_match_the_v0117_baseline(self):
        contract=json.loads((ROOT/'FROZEN_DETECTION_CONTRACT.json').read_text(encoding='utf-8'))
        self.assertEqual(app.DETECTOR_BASELINE_VERSION,contract['detector_baseline_version'])
        nodes={n.name:n for n in ast.parse(inspect.getsource(app)).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        for name,digest in contract['frozen_nodes'].items():
            with self.subTest(function=name):
                self.assertEqual(hashlib.sha256(ast.dump(nodes[name],include_attributes=False).encode()).hexdigest(),digest)
        for name,value in contract['constants'].items():
            with self.subTest(constant=name):self.assertEqual(getattr(app,name),value)
        for name,digest in contract['model_assets'].items():
            with self.subTest(asset=name):self.assertEqual(hashlib.sha256((ROOT/'models'/name).read_bytes()).hexdigest(),digest)

    def test_release_identity_is_derived_from_app_version(self):
        info=release_identity();self.assertEqual(info['APP_VERSION'],app.APP_VERSION)
        self.assertEqual(info['APP_TAG'],'v'+app.APP_VERSION.replace('.',''))
        self.assertEqual(info['APP_NAME'],'HVAC_Territory_Discovery_'+info['APP_TAG'])

    def test_future_release_does_not_require_old_test_version_edits(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'app.py';path.write_text("APP_VERSION='0.11.99'\n",encoding='utf-8')
            self.assertEqual(release_identity(path)['APP_NAME'],'HVAC_Territory_Discovery_v01199')

    def test_release_docs_match_app_and_required_build_files_exist(self):
        info=release_identity()
        self.assertIn('v'+info['APP_VERSION'],(ROOT/'README.txt').read_text(encoding='utf-8').splitlines()[0])
        for name in ('CHANGELOG_'+info['APP_TAG']+'.txt','REGRESSION_NOTES_'+info['APP_TAG']+'.txt',
                     'territories.py','release_identity.py','MODEL_CARD.txt','requirements.txt'):
            with self.subTest(file=name):self.assertTrue((ROOT/name).is_file())

    def test_workflow_does_not_run_stale_version_specific_tests(self):
        workflow=(ROOT/'.github/workflows/build-windows.yml').read_text(encoding='utf-8')
        self.assertIn('python release_identity.py',workflow)
        self.assertIn('--name %APP_NAME%',workflow)
        self.assertIn('${{ env.APP_NAME }}_Windows.zip',workflow)
        self.assertIn('test_detection_logic.py test_territories.py test_release_contract.py',workflow)
        self.assertNotIn('test_v0117_logic.py',workflow);self.assertNotIn('HVAC_Territory_Discovery_v0117',workflow)


if __name__=='__main__':
    unittest.main()
