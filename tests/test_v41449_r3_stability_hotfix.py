from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def text(p): return (ROOT/p).read_text(encoding='utf-8')

def test_po_nameerror_and_escalation_ui():
 s=text('app_pages/supply_chain.py')
 assert 'def _quantity_text(value: Any)' in s
 assert 'Level 2 Employee' in s and 'Level 2 Email' in s and 'Pending Days' in s

def test_cookie_only_auth_no_components_v2_mount():
 s=text('core/auth.py')
 chunk=s[s.index('def _persistent_auth_component'):s.index('def _context_cookie')]
 assert 'return None' in chunk
 assert 'second/blank' in chunk
 assert 'height=0' in s and 'width=0' in s

def test_osp_save_and_metlab_compact_nonapplicable():
 osp=text('app_pages/osp_inspections.py')
 assert '"disposition": disposition' in osp
 assert 'QCMS did not receive a saved report ID from the database.' in osp
 assert 'Unable to save OSP' in osp
 met=text('app_pages/metlab_report.py')
 assert 'Case Depth / Microhardness Traverse: Not applicable for this approved layout.' in met

def test_po_overdue_worker_level_two():
 s=text('supabase/functions/qcms-overdue-notifier/index.ts')
 for token in ['escalation_employee_ids','overdue_level2_employee_id','overdue_level1_employee_id','qcms_module_approval_routes','pendingDays >= 2']:
  assert token in s

def test_first_app_github_build_on_main():
 wf=text('.github/workflows/qcms-first-app-apk.yml')
 java=text('mobile/android_first_app/app/src/main/java/com/fourstar/qcms/MainActivity.java')
 for token in ['workflow_dispatch:','push:','branches: [main]',"java-version: '17'",':app:assembleDebug :app:lintDebug','QCMS-FIRST-APP-APK']:
  assert token in wf
 assert 'QCMSClassicShell/1.0.2' in java
 assert '__qcmsNativeNavigate' not in java
