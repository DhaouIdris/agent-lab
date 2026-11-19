import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from experiments.audit_campaign import consistency_by_case, load_cases
from experiments.benchmark_reporting import save_report


class AuditConsistencyTests(unittest.TestCase):
    def row(self, repetition, passed=True, abstain=False, documents=(), tools=()):
        return {'id':'sample','category':'documents','repetition':repetition,
                'status':'model_output','automatic_checks_pass':passed,
                'observed_tools':list(tools),
                'output':{'answer':'PRIVATE_TEXT','abstain':abstain,
                          'document_ids':list(documents),'place_ids':[]}}

    def test_a_single_failed_repetition_prevents_consistent_success(self):
        rows=[self.row(1),self.row(2,passed=False),self.row(3)]
        result=consistency_by_case(rows,[{'id':'sample','category':'documents'}],3)[0]
        self.assertFalse(result['all_repetitions_passed'])
        self.assertEqual(result['automatic_passes'],2)
        self.assertEqual(result['automatic_checks_evaluable'],3)

    def test_partial_or_duplicate_repetitions_do_not_count_as_complete(self):
        cases=[{'id':'sample','category':'documents'},{'id':'unvisited','category':'documents'}]
        for rows in ([self.row(1),self.row(2)],[self.row(1),self.row(1),self.row(2)]):
            summary=consistency_by_case(rows,cases,3)
            self.assertIsNone(summary[0]['all_repetitions_passed'])
            self.assertIsNone(summary[1]['all_repetitions_passed'])
            self.assertEqual(summary[1]['runs_recorded'],0)

    def test_reports_variations_without_exporting_private_content_or_source_ids(self):
        rows=[self.row(1,documents=('PRIVATE_DOC',),tools=('search_documents',)),
              self.row(2,abstain=True),
              self.row(3,documents=('OTHER_PRIVATE_DOC',),tools=('search_documents',))]
        cases=[{'id':'sample','category':'documents'}]
        summary=consistency_by_case(rows,cases,3)
        self.assertTrue(summary[0]['variable_abstention'])
        self.assertEqual(summary[0]['tool_sequence_variants'],2)
        self.assertEqual(summary[0]['citation_set_variants'],3)
        with tempfile.TemporaryDirectory() as d:
            save_report(Path(d),{'results':rows,'per_case':summary})
            text=(Path(d)/'report.json').read_text(encoding='utf8')
        self.assertNotIn('PRIVATE_DOC',text)
        self.assertNotIn('PRIVATE_TEXT',text)

    def test_cli_interleaves_twelve_cases_and_reports_pending_external_evaluation(self):
        manifest=Path('data/audit_consistency_12.json')
        cases=load_cases(manifest,True)
        self.assertEqual(len(cases),12)
        self.assertTrue(all(c['abstain_is_diagnostic'] for c in cases))
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'run'
            process=subprocess.run([sys.executable,'-m','experiments.audit_campaign','--cases',str(manifest),
                                    '--consistency','--out',str(out)],capture_output=True,text=True,encoding='utf8')
            self.assertEqual(process.returncode,0,process.stderr)
            report=json.loads((out/'report.json').read_text(encoding='utf8'))
        self.assertTrue(report['campaign_complete'])
        self.assertEqual(report['summary']['provider_attempts'],0)
        self.assertEqual(report['summary']['automatic_passes'],6)
        self.assertEqual(report['summary']['cases_passed_all_repetitions'],2)
        self.assertEqual(report['summary']['cases_awaiting_complete_evaluation'],10)
        self.assertEqual(report['summary']['statuses']['awaiting_chat'],27)
        self.assertEqual(report['summary']['statuses']['awaiting_route'],3)
        expected=[(c['id'],repetition) for repetition in range(1,4) for c in cases]
        self.assertEqual([(r['id'],r['repetition']) for r in report['results']],expected)
        self.assertEqual(len(report['per_case']),12)
