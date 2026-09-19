import ast
import hashlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import app
from release_identity import release_identity


ROOT=Path(__file__).resolve().parent


def model_asset_sha256(path):
    """Ignore Git's CRLF checkout conversion for JSON; keep binary hashes exact."""
    data=path.read_bytes()
    if path.suffix.lower()=='.json':
        data=data.replace(b'\r\n',b'\n')
    return hashlib.sha256(data).hexdigest()


def validate_checkpoint_archive(path):
    """Check the checkpoint's directory, tensor records, and every member's CRC."""
    try:
        with ZipFile(path) as archive:
            names=archive.namelist()
            if not any(name.endswith('/data.pkl') for name in names):
                raise ValueError('missing PyTorch state metadata')
            if not any('/data/' in name and not name.endswith('/') for name in names):
                raise ValueError('missing tensor storage records')
            damaged=archive.testzip()
            if damaged is not None:
                raise ValueError('damaged archive member: '+damaged)
    except (BadZipFile,OSError,RuntimeError,ValueError) as error:
        raise ValueError(f'Invalid model checkpoint {path}: {error}') from error


class ReleaseContractTests(unittest.TestCase):
    def test_frozen_core_models_and_v0119_logic_match_the_release_contract(self):
        contract=json.loads((ROOT/'FROZEN_DETECTION_CONTRACT.json').read_text(encoding='utf-8'))
        self.assertEqual(app.DETECTOR_BASELINE_VERSION,contract['detector_baseline_version'])
        self.assertEqual(app.TERRITORY_LOGIC_VERSION,contract['territory_logic_version'])
        nodes={n.name:n for n in ast.parse(inspect.getsource(app)).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        for name,digest in contract['frozen_nodes'].items():
            with self.subTest(function=name):
                self.assertEqual(hashlib.sha256(ast.dump(nodes[name],include_attributes=False).encode()).hexdigest(),digest)
        for name,value in contract['constants'].items():
            with self.subTest(constant=name):self.assertEqual(getattr(app,name),value)
        for name,digest in contract['model_assets'].items():
            with self.subTest(asset=name):self.assertEqual(model_asset_sha256(ROOT/'models'/name),digest)

    def test_model_checkpoint_archives_are_complete_and_readable(self):
        for name in ('candidate.pt','resnet18_embedder_state_fp16.pt'):
            with self.subTest(asset=name):validate_checkpoint_archive(ROOT/'models'/name)

    def test_checkpoint_validation_rejects_missing_central_directory(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'truncated.pt'
            with ZipFile(path,'w') as archive:
                archive.writestr('fixture/data.pkl',b'state metadata')
                archive.writestr('fixture/data/0',b'tensor bytes')
            validate_checkpoint_archive(path)
            path.write_bytes(path.read_bytes()[:-22])
            with self.assertRaisesRegex(ValueError,'truncated.pt'):
                validate_checkpoint_archive(path)

    def test_checkpoint_validation_rejects_corrupt_tensor_with_intact_directory(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'corrupt.pt';tensor=b'unique-tensor-bytes-for-CRC-test'
            with ZipFile(path,'w') as archive:
                archive.writestr('fixture/data.pkl',b'state metadata')
                archive.writestr('fixture/data/0',tensor)
            data=path.read_bytes();self.assertEqual(data.count(tensor),1)
            path.write_bytes(data.replace(tensor,b'X'+tensor[1:]))
            with self.assertRaisesRegex(ValueError,'fixture/data/0'):
                validate_checkpoint_archive(path)

    def test_checkpoint_validation_rejects_generic_zip_without_model_records(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'not-a-model.pt'
            with ZipFile(path,'w') as archive:archive.writestr('README.txt','not a checkpoint')
            with self.assertRaisesRegex(ValueError,'missing PyTorch state metadata'):
                validate_checkpoint_archive(path)

    def test_json_asset_hashes_accept_lf_crlf_and_mixed_line_endings(self):
        contract=json.loads((ROOT/'FROZEN_DETECTION_CONTRACT.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as td:
            for name,digest in contract['model_assets'].items():
                if Path(name).suffix.lower()!='.json':continue
                data=(ROOT/'models'/name).read_bytes().replace(b'\r\n',b'\n')
                variants={
                    'LF':data,
                    'CRLF':data.replace(b'\n',b'\r\n'),
                    'mixed':data.replace(b'\n',b'\r\n',1),
                }
                for ending,content in variants.items():
                    with self.subTest(asset=name,line_endings=ending):
                        path=Path(td)/name;path.write_bytes(content)
                        self.assertEqual(model_asset_sha256(path),digest)

    def test_json_asset_hashes_reject_value_and_other_content_changes(self):
        original=b'{\n  "threshold": 0.35\n}\n'
        expected=hashlib.sha256(original).hexdigest()
        changes={
            'value':original.replace(b'0.35',b'0.36'),
            'value_with_CRLF':original.replace(b'0.35',b'0.36').replace(b'\n',b'\r\n'),
            'indentation':original.replace(b'  "',b' "'),
            'missing_final_newline':original.rstrip(b'\n'),
        }
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'pipeline_config.json'
            for change,content in changes.items():
                with self.subTest(change=change):
                    path.write_bytes(content)
                    self.assertNotEqual(model_asset_sha256(path),expected)

    def test_binary_asset_hashes_remain_byte_exact(self):
        original=b'model\x00\xff\nweights\r\n'
        expected=hashlib.sha256(original).hexdigest()
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'candidate.pt';path.write_bytes(original)
            self.assertEqual(model_asset_sha256(path),expected)
            for content in (original.replace(b'\n',b'\r\n'),original.replace(b'\r\n',b'\n'),original+b'\x00'):
                path.write_bytes(content)
                self.assertNotEqual(model_asset_sha256(path),expected)

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
        self.assertIn('Source model loading smoke test',workflow)
        self.assertIn('Bundled model loading smoke test',workflow)
        self.assertIn('app.LocalCV()',workflow)
        self.assertIn('Get-FileHash',workflow)
        self.assertIn('MODEL_BUNDLE_BASE',workflow)
        self.assertNotIn('test_v0117_logic.py',workflow);self.assertNotIn('HVAC_Territory_Discovery_v0117',workflow)


if __name__=='__main__':
    unittest.main()
