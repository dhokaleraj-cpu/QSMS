from io import BytesIO
from pathlib import Path
import copy
import json
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pytest
from pypdf import PdfReader
from core.purchase_order_reporting import (
    purchase_order_pdf_bytes, purchase_order_pdf_files, purchase_order_files_zip_bytes,
)
from test_v41433_po_portrait_batch_android_sdk import _payload

ROOT = Path(__file__).resolve().parents[1]
NO_TERMS = ROOT / 'tests' / '__missing_terms_v41434.pdf'


def two_pos():
    a = _payload('PO-ONE-41434'); b = _payload('PO-TWO-41434')
    a[0]['id'] = 'id-one'; b[0]['id'] = 'id-two'
    a[0]['vendor_snapshot']['party_name'] = 'ONLY SUPPLIER ALPHA'
    b[0]['vendor_snapshot']['party_name'] = 'ONLY SUPPLIER BETA'
    return [a, b]


def pdf_text(blob):
    return '\n'.join(p.extract_text() or '' for p in PdfReader(BytesIO(blob)).pages)


def test_v41434_controlled_release_identity():
    manifest = json.loads((ROOT / 'DEPLOYMENT_MANIFEST.json').read_text())
    assert (ROOT / 'VERSION').read_text().strip() == manifest['version'] in {'4.14.34','4.14.35', '4.14.36', '4.14.37'}
    if manifest['version'] == '4.14.37':
        assert manifest['build'] == '41437-MOBILE-FULL-NAV-COMPLAINT-CARDS-PO-APPROVAL-DRAFT-EMAIL'
        assert manifest['previous_controlled_release'] == '4.14.36'
        assert manifest['database_schema_required'] == '4.14.36'
        assert manifest['database_migration_required'] is True
    elif manifest['version'] == '4.14.36':
        assert manifest['build'] == '41436-COMPLAINT-EMAIL-REGISTERS-REMINDERS-MOBILE-DRAWER'
        assert manifest['previous_controlled_release'] == '4.14.35'
        assert manifest['database_schema_required'] == '4.14.36'
        assert manifest['database_migration_required'] is True
    elif manifest['version'] == '4.14.35':
        assert manifest['build'] == '41435-PO-WATERMARK-REMINDER-MOBILE-IOS'
        assert manifest['previous_controlled_release'] == '4.14.34'
        assert manifest['database_schema_required'] == '4.14.35'
        assert manifest['database_migration_required'] is True
    else:
        assert manifest['build'] == '41434-INDIVIDUAL-PO-PDF-ZIP-ANDROID-APK-BUILD'
        assert manifest['previous_controlled_release'] == '4.14.33'
        assert manifest['database_schema_required'] == '4.14.28'
        assert manifest['database_migration_required'] is False
    assert manifest['android_apk_compiled_in_preparation'] is False


def test_each_selected_po_gets_its_own_complete_original_pdf():
    records = two_pos(); before = copy.deepcopy(records)
    result = purchase_order_pdf_files(records, terms_path=NO_TERMS)
    assert [n for n, _ in result] == ['PO-ONE-41434.pdf', 'PO-TWO-41434.pdf']
    # Only each selected PO's own document appears in its own file.
    assert 'PO-ONE-41434' in pdf_text(result[0][1])
    assert 'PO-TWO-41434' not in pdf_text(result[0][1])
    assert 'ONLY SUPPLIER ALPHA' in pdf_text(result[0][1])
    assert 'ONLY SUPPLIER BETA' not in pdf_text(result[0][1])
    assert 'PO-TWO-41434' in pdf_text(result[1][1])
    assert 'PO-ONE-41434' not in pdf_text(result[1][1])
    assert records == before


def test_zip_contains_separate_pdfs_with_unchanged_bytes():
    result = purchase_order_pdf_files(two_pos(), terms_path=NO_TERMS)
    archive = purchase_order_files_zip_bytes(result)
    with ZipFile(BytesIO(archive)) as z:
        assert z.testzip() is None
        assert z.namelist() == [n for n, _ in result]
        for name, original_pdf in result:
            assert z.read(name) == original_pdf
            assert len(PdfReader(BytesIO(z.read(name))).pages) == 1


def test_physical_copies_repeat_only_inside_each_po_not_across_pos():
    result = purchase_order_pdf_files(two_pos(), copies_per_order=3, terms_path=NO_TERMS)
    assert len(result) == 2
    for index, (_, pdf) in enumerate(result):
        assert len(PdfReader(BytesIO(pdf)).pages) == 3
        assert pdf_text(pdf).count('PO-ONE-41434' if index == 0 else 'PO-TWO-41434') >= 3
        assert ('PO-TWO-41434' if index == 0 else 'PO-ONE-41434') not in pdf_text(pdf)


def test_each_po_has_its_own_portrait_terms():
    result = purchase_order_pdf_files(two_pos())
    for _, pdf in result:
        pages = PdfReader(BytesIO(pdf)).pages
        assert 7 <= len(pages) <= 9
        assert all(float(p.mediabox.width) < float(p.mediabox.height) for p in pages)
        assert 'TERMS' in (pages[-1].extract_text() or '').upper()


def test_repeated_saved_po_id_does_not_create_duplicate_file():
    records = two_pos(); records += [records[0]]
    assert len(purchase_order_pdf_files(records, terms_path=NO_TERMS)) == 2


def test_different_ids_with_same_print_number_get_distinct_files():
    a, b = two_pos(); b[0]['po_number'] = a[0]['po_number'].lower()
    result = purchase_order_pdf_files([a, b], terms_path=NO_TERMS)
    assert len({n.casefold() for n, _ in result}) == 2
    assert result[1][0].endswith('__2.pdf')


@pytest.mark.parametrize('number', ['../../PO/1', r'C:\\PO\\2', 'CON', 'LPT1', '.', 'A'*300, 'PO:1?*'])
def test_filenames_are_safe_on_mac_android_and_windows(number):
    a = two_pos()[0]; a[0]['po_number'] = number
    result = purchase_order_pdf_files([a], terms_path=NO_TERMS)
    name = result[0][0]
    assert '/' not in name and '\\' not in name
    assert not name.startswith('.') and len(name) <= 110
    assert name.split('.')[0].upper() not in {'CON', 'LPT1'}
    with ZipFile(BytesIO(purchase_order_files_zip_bytes(result))) as z:
        assert z.namelist() == [name]


@pytest.mark.parametrize('copies', [0, 6, -1, True, 1.5, '2'])
def test_invalid_copy_counts_are_not_silently_changed(copies):
    with pytest.raises(ValueError, match='Copies per PO'):
        purchase_order_pdf_files(two_pos(), copies_per_order=copies, terms_path=NO_TERMS)


def test_empty_selection_and_missing_items_fail_clearly():
    with pytest.raises(ValueError, match='Select at least'):
        purchase_order_pdf_files([])
    a, b = two_pos()
    with pytest.raises(ValueError, match='no printable'):
        purchase_order_pdf_files([a, (b[0], [])], terms_path=NO_TERMS)
    with pytest.raises(ValueError, match='not accessible'):
        purchase_order_pdf_files([({}, a[1])], terms_path=NO_TERMS)
    with pytest.raises(ValueError, match='No Purchase Order'):
        purchase_order_files_zip_bytes([])


def test_zip_rejects_paths_duplicates_and_non_pdf_content():
    pdf = purchase_order_pdf_files([two_pos()[0]], terms_path=NO_TERMS)[0][1]
    for files in [[('../bad.pdf', pdf)], [('a.pdf', pdf), ('A.pdf', pdf)], [('bad.pdf', b'not-pdf')]]:
        with pytest.raises(ValueError):
            purchase_order_files_zip_bytes(files)


def test_batch_ui_no_longer_combines_different_purchase_orders():
    source = (ROOT / 'app_pages/supply_chain.py').read_text()
    assert 'purchase_order_pdf_files(records, copies_per_order=copies)' in source
    assert 'purchase_order_files_zip_bytes(po_files)' in source
    assert 'batch_purchase_order_pdf_bytes(' not in source
    assert 'Individual PO PDFs (ZIP)' in source
    assert 'Individual PDF downloads' in source
    assert 'No incomplete batch has been offered for download' in source
    assert 'Confirm Batch Purchase Order Emails' in source


def test_android_ci_is_read_only_and_uploads_only_verified_apk():
    workflow = (ROOT / '.github/workflows/qcms-android-test-apk.yml').read_text()
    for token in ['workflow_dispatch:', 'contents: read', ':app:assembleDebug', ':app:lintDebug',
                  'apksigner', 'verify --verbose', 'zipalign', 'actions/upload-artifact@v4',
                  'if-no-files-found: error', 'QCMS_Mobile_v0.1.2_TEST.apk' if (ROOT / 'VERSION').read_text().strip() == '4.14.34' else 'QCMS_Mobile_v0.1.3_TEST.apk' if (ROOT / 'VERSION').read_text().strip() == '4.14.35' else 'QCMS_Mobile_v0.1.4_TEST.apk']:
        assert token in workflow
    assert 'pull_request_target' not in workflow
    assert 'SUPABASE' not in workflow
    ET.parse(ROOT / 'mobile/android_qcms/app/src/main/AndroidManifest.xml')
    helper = (ROOT / 'mobile/android_qcms/BUILD_AND_INSTALL_SAMSUNG.command').read_text()
    assert 'QCMS_BUILD_ONLY' in helper
    expected_apk = ('$HOME/Downloads/QCMS_Mobile_v0.1.5_TEST.apk' if (ROOT / 'VERSION').read_text().strip() == '4.14.37' else ('$HOME/Downloads/QCMS_Mobile_v0.1.4_TEST.apk' if (ROOT / 'VERSION').read_text().strip() == '4.14.36' else ('$HOME/Downloads/QCMS_Mobile_v0.1.3_TEST.apk' if (ROOT / 'VERSION').read_text().strip() == '4.14.35' else '$HOME/Downloads/QCMS_Mobile_v0.1.2_TEST.apk')))
    assert expected_apk in helper
    source = (ROOT / 'mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java').read_text()
    assert 'Settings.ACTION_WEBVIEW_SETTINGS' not in source
    expected_ua = ('QCMSMobile/0.1.5' if (ROOT / 'VERSION').read_text().strip() == '4.14.37' else ('QCMSMobile/0.1.4' if (ROOT / 'VERSION').read_text().strip() == '4.14.36' else ('QCMSMobile/0.1.3' if (ROOT / 'VERSION').read_text().strip() == '4.14.35' else 'QCMSMobile/0.1.2')))
    assert expected_ua in source
