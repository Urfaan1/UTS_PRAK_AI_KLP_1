"""Forward chaining deterministik dengan provenance untuk menghindari bukti ganda."""
import copy
import math
import uuid
from datetime import datetime, timezone, timedelta

class WorkingMemory:
    """Fakta, kontribusi aturan, dan trace untuk satu sesi saja."""
    def __init__(self, answers):
        """Simpan hanya jawaban positif sebagai fakta pendukung."""
        self.facts = {g: {'cf': a['cf'], 'evidence': {g}, 'rule_ids': set()} for g, a in answers.items() if a['answer'] == 'yes'}
        self.contributions = {}
        self.trace = []

class MesinPakar:
    """Hitung graf aturan acyclic secara topologis melalui forward chaining."""
    def __init__(self, kb):
        """Snapshot memastikan hasil tidak berubah oleh edit aturan berikutnya."""
        self.kb = copy.deepcopy(kb)

    @staticmethod
    def combine(contributions):
        """Gabung greedy dukungan positif; bukti beririsan dilewati."""
        value, used, accepted, skipped = 0.0, set(), [], []
        for c in sorted(contributions, key=lambda x: (-x['cf'], x['rule_id'])):
            if used & c['evidence']:
                skipped.append(c['rule_id'])
                continue
            value = value + c['cf'] * (1 - value)
            used |= c['evidence']
            accepted.append(c)
        return value, used, accepted, skipped

    def run(self, answers):
        """Validasi jawaban, jalankan inferensi, dan hasilkan snapshot serializable."""
        expected = {g['id'] for g in self.kb['symptoms']}
        if set(answers) != expected:
            raise ValueError('Jawaban harus memuat seluruh kode gejala.')
        for a in answers.values():
            if not isinstance(a, dict) or a.get('answer') not in ('yes', 'no', 'unknown'):
                raise ValueError('Jawaban tidak valid.')
            cf = a.get('cf')
            if a['answer'] == 'yes':
                if isinstance(cf, bool) or not isinstance(cf, (int, float)) or not math.isfinite(cf) or not 0 < cf <= 1:
                    raise ValueError('CF gejala harus > 0 sampai 1.')
            elif cf is not None:
                raise ValueError('Jawaban Tidak/Tidak tahu tidak boleh memiliki CF.')
        if not any(a['answer'] == 'yes' for a in answers.values()):
            raise ValueError('Pilih minimal satu gejala yang dialami.')
        wm = WorkingMemory(answers)
        rules = sorted(self.kb['rules'], key=lambda r: r['id'])
        pending = {r['id']: r for r in rules}
        # Finalize a consequent only after every possible producer has settled.
        # This avoids a downstream rule using a stale intermediate CF.
        while pending:
            ready = [r for r in pending.values() if all(not any(p['then'] == a for p in pending.values()) for a in r['if'])]
            if not ready:
                raise ValueError('Graf aturan melingkar.')
            targets = set()
            for r in ready:
                del pending[r['id']]
                targets.add(r['then'])
                if not all(a in wm.facts for a in r['if']):
                    continue
                facts = [wm.facts[a] for a in r['if']]
                c = {'rule_id': r['id'], 'cf': min(f['cf'] for f in facts) * r['cf'], 'evidence': set().union(*(f['evidence'] for f in facts)), 'rule_ids': {r['id']} | set().union(*(f['rule_ids'] for f in facts))}
                wm.contributions[r['id']] = (r['then'], c)
                wm.trace.append({'step': len(wm.trace)+1, 'rule_id': r['id'], 'if': r['if'], 'then': r['then'], 'inputs': {a: wm.facts[a]['cf'] for a in r['if']}, 'rule_cf': r['cf'], 'cf': c['cf'], 'evidence': sorted(c['evidence']), 'combination': ''})
            for target in targets:
                if any(r['then'] == target for r in pending.values()):
                    continue
                cs = [c for t,c in wm.contributions.values() if t == target]
                if not cs:
                    continue
                value, evidence, accepted, skipped = self.combine(cs)
                wm.facts[target] = {'cf': value, 'evidence': evidence, 'rule_ids': set().union(*(c['rule_ids'] for c in accepted))}
                accepted_ids = {c['rule_id'] for c in accepted}
                for t in wm.trace:
                    if t['then'] == target:
                        t['combination'] = 'Dipakai dalam hasil gabungan' if t['rule_id'] in accepted_ids else 'Tidak digabung: bukti tumpang tindih'
        results = []
        for d in self.kb['diagnoses']:
            code = d['id']
            if code not in wm.facts or (code == 'K05' and answers['G13']['answer'] == 'yes'):
                continue
            f = wm.facts[code]
            src = sorted({s for r in rules if r['id'] in f['rule_ids'] for s in r['source_ids']})
            results.append({'code': code, 'name': d['name'], 'description': d['description'], 'recommendations': d['recommendations'], 'cf': f['cf'], 'supporting_symptoms': sorted(f['evidence']), 'rule_ids': sorted(f['rule_ids']), 'source_ids': src})
        results.sort(key=lambda d: (-d['cf'], d['code']))
        alerts = []
        if any(answers[g]['answer'] == 'yes' for g in ('G16','G17')):
            alerts.append('Hentikan operasi. Bau terbakar atau MCB berulang terputus memerlukan pemeriksaan teknisi; jangan terus menyalakan AC.')
        return {'consultation_id': str(uuid.uuid4()), 'created_at': datetime.now(timezone(timedelta(hours=7))).isoformat(timespec='seconds'), 'knowledge_version': self.kb['version'], 'status': 'diagnosed' if results else 'inconclusive', 'answers': copy.deepcopy(answers), 'alerts': alerts, 'diagnoses': results, 'trace': wm.trace, 'knowledge_snapshot': self.kb, 'working_memory': {k: {'cf':v['cf'], 'evidence':sorted(v['evidence'])} for k,v in wm.facts.items()}}
