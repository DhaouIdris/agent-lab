"""The corrected development panel changes two labels without rewriting the old file."""
import json
import unittest
from pathlib import Path

from experiments.audit_campaign import load_cases


class NaturalPanelV2Tests(unittest.TestCase):
    def test_corrected_labels_and_frozen_original(self):
        old=json.loads(Path('data/natural_user_expansion_36.json').read_text(encoding='utf8'))
        new=json.loads(Path('data/natural_user_expansion_36_v2.json').read_text(encoding='utf8'))
        self.assertEqual(len(old),len(new))
        changed={a['id'] for a,b in zip(old,new) if a!=b}
        self.assertEqual(changed,{'E-D01','E-A06'})
        rows={row['id']:row for row in load_cases(Path('data/natural_user_expansion_36_v2.json'),False)}
        self.assertEqual(rows['E-D01']['evidence_checks']['required_document_ids'],['UNESCO_BASSAM__0003'])
        self.assertFalse(rows['E-A06']['required_tools'])
        self.assertEqual(rows['E-A06']['goal'],'general')


if __name__=='__main__':
    unittest.main()
