"""Pengujian perilaku menggunakan data dan database sementara."""
import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from mesin_pakar import MesinPakar
from penyimpanan import Penyimpanan, export_txt, BASE

class SistemTest(unittest.TestCase):
    """Kasus inferensi, provenance, CRUD, dan snapshot."""
    def setUp(self):
        """Salin data awal; jangan mutasi proyek pengguna."""
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for file in ('gejala.json','kerusakan.json','aturan.json'):
            shutil.copy(BASE/file,self.root/file)
        self.repo = Penyimpanan(self.root)
        self.kb = self.repo.load()

    def tearDown(self):
        """Bersihkan database dan data pengujian."""
        self.tmp.cleanup()

    def run_case(self, *positive, confidence=1.):
        """Jalankan gejala terpilih dengan nilai CF seragam."""
        answers = {g['id']:{'answer':'yes' if g['id'] in positive else 'unknown','cf':confidence if g['id'] in positive else None} for g in self.kb['symptoms']}
        return MesinPakar(self.kb).run(answers)

    def test_chain_and_fractional_cf(self):
        """Fakta sementara harus diteruskan dengan perkalian CF."""
        r = self.run_case('G02','G03',confidence=.8)
        self.assertAlmostEqual(r['working_memory']['I01']['cf'],.72)
        self.assertAlmostEqual(r['diagnoses'][0]['cf'],.648)
        self.assertEqual([t['rule_id'] for t in r['trace']],['R01','R02'])

    def test_initial_cases(self):
        """Periksa hasil utama beserta nilai manual."""
        for symptoms, code, cf in [(('G01','G04','G05'),'K02',.975),(('G01','G06'),'K03',.85),(('G07','G08','G09'),'K04',.9),(('G11','G12'),'K05',.8),(('G14','G15'),'K07',.75),(('G16',),'K08',.95),(('G01','G02','G03'),'K01',.81)]:
            with self.subTest(symptoms=symptoms):
                r = self.run_case(*symptoms)
                self.assertEqual(r['diagnoses'][0]['code'],code)
                self.assertAlmostEqual(r['diagnoses'][0]['cf'],cf)

    def test_override_alert_and_inconclusive(self):
        """Periksa prioritas remote, alarm, dan fakta yang belum lengkap."""
        r = self.run_case('G11','G12','G13')
        self.assertEqual([d['code'] for d in r['diagnoses']],['K06'])
        self.assertTrue(self.run_case('G16',confidence=.4)['alerts'])
        self.assertEqual(self.run_case('G01')['status'],'inconclusive')

    def test_empty_invalid_input(self):
        """Input kosong atau CF nonfinite harus ditolak."""
        with self.assertRaises(ValueError):
            self.run_case()
        with self.assertRaises(ValueError):
            self.run_case('G01',confidence=float('nan'))

    def test_history_snapshot_export_and_idempotency(self):
        """Simpan sekali dan pertahankan aturan lama pada ekspor."""
        r = self.run_case('G02','G03')
        self.repo.save_result(r)
        self.repo.save_result(r)
        rules = copy.deepcopy(self.kb['rules'])
        rules[0]['cf'] = .5
        self.repo.save_rules(rules,1)
        stored = self.repo.history()[0]
        self.assertEqual(len(self.repo.history()),1)
        self.assertEqual(stored['knowledge_version'],1)
        self.assertEqual(stored['knowledge_snapshot']['rules'][0]['cf'],.9)
        self.assertIn('81.0%',export_txt(stored))
        self.assertEqual(self.repo.statistics()['rules'],{'R01':1,'R02':1})

    def test_rule_crud_and_conflict(self):
        """Tambah/edit/hapus tersimpan dan edit dari versi lama ditolak."""
        rules = copy.deepcopy(self.kb['rules'])
        new = dict(id='R16',**{'if':['G03'],'then':'K01','cf':.5,'source_ids':['S01']})
        rules.append(new)
        self.repo.save_rules(rules,1)
        self.assertEqual(len(self.repo.load()['rules']),16)
        with self.assertRaises(ValueError):
            self.repo.save_rules(rules,1)
        rules[-1]['cf'] = .6
        self.repo.save_rules(rules,2)
        self.repo.save_rules(rules[:-1],3)
        self.assertEqual(len(self.repo.load()['rules']),15)

    def test_rule_validation(self):
        """Tolak duplikasi, referensi salah, orphan, CF buruk, dan siklus."""
        for change in ('duplicate','unknown','orphan','cf','cycle'):
            kb = copy.deepcopy(self.kb)
            if change == 'duplicate':
                r = copy.deepcopy(kb['rules'][0]); r['id']='R99'; r['if'].reverse(); kb['rules'].append(r)
            elif change == 'unknown':
                kb['rules'][0]['if']=['G99']
            elif change == 'orphan':
                kb['rules'] = kb['rules'][1:]
            elif change == 'cf':
                kb['rules'][0]['cf']=2
            else:
                kb['rules'][0]['if']=['I01']
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.repo.validate(kb)

    @unittest.skipUnless(importlib.util.find_spec('streamlit'),'Streamlit belum terpasang')
    def test_gui_consultation_navigation_search_reset(self):
        """Jalankan tiga halaman dan konsultasi tanpa browser eksternal."""
        from streamlit.testing.v1 import AppTest
        # App imports modules from the project, but repository writes only here.
        script = '''import streamlit as st
from penyimpanan import Penyimpanan
import konsultasi, basis_pengetahuan, riwayat
repo=Penyimpanan(ROOT)
page=st.radio('Menu',['Konsultasi','Basis','Riwayat'])
{'Konsultasi':konsultasi.render,'Basis':basis_pengetahuan.render,'Riwayat':riwayat.render}[page](repo)
'''.replace('ROOT',repr(str(self.root)))
        at = AppTest.from_string(script).run(timeout=30)
        self.assertFalse(at.exception)
        at.radio(key='answer_G02').set_value('Ya')
        at.radio(key='answer_G03').set_value('Ya')
        at.run()
        at.text_input(key='symptom_search').set_value('remote').run()
        self.assertEqual(at.session_state['answers']['G02']['answer'],'yes')
        next(b for b in at.button if b.label=='Diagnosis Sekarang').click().run()
        self.assertFalse(at.exception)
        self.assertAlmostEqual(at.session_state['result']['diagnoses'][0]['cf'],.648)
        self.assertEqual(len(self.repo.history()),1)
        at.run()
        self.assertEqual(len(self.repo.history()),1)
        at.radio[0].set_value('Basis').run()
        self.assertFalse(at.exception)
        at.radio[0].set_value('Riwayat').run()
        self.assertFalse(at.exception)
        at.radio[0].set_value('Konsultasi').run()
        next(b for b in at.button if b.label=='Reset Jawaban').click().run()
        self.assertFalse(at.exception)
        self.assertNotIn('result',at.session_state)

    @unittest.skipUnless(importlib.util.find_spec('streamlit'),'Streamlit belum terpasang')
    def test_gui_group_state_and_crud(self):
        """Jawaban lintas kelompok bertahan; CRUD aturan bekerja melalui form GUI."""
        from streamlit.testing.v1 import AppTest
        script = """import streamlit as st
from penyimpanan import Penyimpanan
import konsultasi, basis_pengetahuan
repo=Penyimpanan(ROOT)
page=st.radio('Menu',['Konsultasi','Basis'])
{'Konsultasi':konsultasi.render,'Basis':basis_pengetahuan.render}[page](repo)
""".replace('ROOT',repr(str(self.root)))
        at=AppTest.from_string(script).run()
        at.radio(key='answer_G01').set_value('Ya').run()
        at.selectbox(key='symptom_group').set_value('Remote').run()
        at.radio(key='answer_G11').set_value('Ya').run()
        at.selectbox(key='symptom_group').set_value('Pendinginan').run()
        self.assertEqual(at.radio(key='answer_G01').value,'Ya')
        self.assertEqual(at.session_state['answers']['G11']['answer'],'yes')
        at.radio[0].set_value('Basis').run()
        next(x for x in at.text_input if x.label=='Kode aturan').set_value('R16')
        next(x for x in at.multiselect if x.label.startswith('IF')).set_value(['G03'])
        next(x for x in at.selectbox if x.label.startswith('THEN')).set_value('K01')
        next(x for x in at.multiselect if x.label=='Sumber pengetahuan').set_value(['S01'])
        next(x for x in at.button if x.label=='Simpan Perubahan').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(len(self.repo.load()['rules']),16)
        at.radio(key='rule_action').set_value('Edit').run()
        next(x for x in at.selectbox if x.label=='Pilih aturan').set_value('R16').run()
        next(x for x in at.number_input if x.label=='CF aturan').set_value(.7)
        next(x for x in at.button if x.label=='Simpan Perubahan').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(self.repo.load()['rules'][-1]['cf'],.7)
        at.radio(key='rule_action').set_value('Hapus').run()
        next(x for x in at.selectbox if x.label=='Pilih aturan').set_value('R16').run()
        at.checkbox[0].check()
        next(x for x in at.button if x.label=='Hapus Aturan').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(len(self.repo.load()['rules']),15)

if __name__ == '__main__':
    unittest.main()
