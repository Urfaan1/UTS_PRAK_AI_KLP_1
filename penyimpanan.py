"""Repository JSON tervalidasi dan riwayat SQLite; tidak bergantung pada GUI."""
import copy
from contextlib import contextmanager
import json
import math
import os
import sqlite3
import tempfile
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent

class Penyimpanan:
    """Kelola basis pengetahuan serta snapshot konsultasi."""
    def __init__(self, root=BASE):
        """Gunakan folder proyek atau folder sementara untuk pengujian."""
        self.root = Path(root)
        self.db = self.root / 'riwayat.db'
        with self.connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS consultations (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT NOT NULL)')

    @contextmanager
    def connect(self):
        """Transaksi singkat dengan commit/rollback dan koneksi selalu ditutup."""
        conn = sqlite3.connect(self.db, timeout=10)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def load(self):
        """Baca seluruh data dan tolak basis aturan yang tidak valid."""
        try:
            read = lambda name: json.loads((self.root / name).read_text(encoding='utf-8'))
            kb = {'symptoms': read('gejala.json'), **read('kerusakan.json'), **read('aturan.json')}
            self.validate(kb)
            return kb
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError(f'Basis pengetahuan tidak dapat dibaca: {exc}') from exc

    @staticmethod
    def validate(kb):
        """Validasi referensi, CF, duplikasi, graf tanpa siklus, dan fakta antara."""
        symptoms = {x['id'] for x in kb['symptoms']}
        diagnoses = {x['id'] for x in kb['diagnoses']}
        intermediate = set(kb['intermediates'])
        if len(symptoms) != len(kb['symptoms']) or len(diagnoses) != len(kb['diagnoses']):
            raise ValueError('Kode gejala/kerusakan harus unik.')
        if symptoms & diagnoses or symptoms & intermediate or diagnoses & intermediate:
            raise ValueError('Kode fakta harus berbeda antar jenis.')
        sources = {s['id'] for s in kb['sources']}
        ids, signatures = set(), set()
        graph = {x: set() for x in intermediate}
        producers = set()
        for r in kb['rules']:
            rid = r.get('id', '')
            if not isinstance(rid, str) or not rid.strip() or rid in ids:
                raise ValueError('ID aturan wajib terisi dan unik.')
            ids.add(rid)
            ant = r.get('if')
            if not isinstance(ant, list) or not ant or not all(isinstance(x, str) for x in ant) or len(set(ant)) != len(ant):
                raise ValueError(f'{rid}: IF wajib berisi fakta unik.')
            if not set(ant) <= symptoms | intermediate:
                raise ValueError(f'{rid}: syarat tidak dikenal atau memakai diagnosis akhir.')
            if r.get('then') not in intermediate | diagnoses:
                raise ValueError(f'{rid}: THEN tidak dikenal.')
            cf = r.get('cf')
            if isinstance(cf, bool) or not isinstance(cf, (int, float)) or not math.isfinite(cf) or not 0 < cf <= 1:
                raise ValueError(f'{rid}: CF harus > 0 sampai 1.')
            src = r.get('source_ids')
            if not isinstance(src, list) or not src or not set(src) <= sources:
                raise ValueError(f'{rid}: sumber tidak valid.')
            sig = (tuple(sorted(ant)), r['then'])
            if sig in signatures:
                raise ValueError('Aturan duplikat secara logis.')
            signatures.add(sig)
            if r['then'] in intermediate:
                producers.add(r['then'])
                for a in ant:
                    if a in intermediate:
                        graph[a].add(r['then'])
        referenced = {a for r in kb['rules'] for a in r['if'] if a in intermediate}
        if not referenced <= producers:
            raise ValueError('Ada fakta sementara tanpa aturan pembentuk.')
        visiting, done = set(), set()
        def visit(node):
            if node in visiting:
                raise ValueError('Aturan melingkar tidak diperbolehkan.')
            if node in done:
                return
            visiting.add(node)
            for nxt in graph[node]:
                visit(nxt)
            visiting.remove(node)
            done.add(node)
        for node in graph:
            visit(node)

    def save_rules(self, rules, expected_version):
        """Validasi lalu simpan atomik; versi lama ditolak untuk mencegah overwrite."""
        kb = self.load()
        if kb['version'] != expected_version:
            raise ValueError('Aturan telah berubah. Muat ulang halaman sebelum menyimpan.')
        kb['rules'] = copy.deepcopy(rules)
        self.validate(kb)
        data = {'version': kb['version'] + 1, 'rules': rules}
        fd, temp = tempfile.mkstemp(dir=self.root, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            os.replace(temp, self.root / 'aturan.json')
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def save_result(self, result):
        """Simpan UUID sekali; rerun GUI tidak menduplikasi konsultasi."""
        with self.connect() as conn:
            conn.execute('INSERT OR IGNORE INTO consultations VALUES (?, ?, ?, ?)', (result['consultation_id'], result['created_at'], result['status'], json.dumps(result, ensure_ascii=False, allow_nan=False)))

    def history(self):
        """Ambil snapshot hasil dari yang paling baru."""
        with self.connect() as conn:
            return [json.loads(row[0]) for row in conn.execute('SELECT result_json FROM consultations ORDER BY created_at DESC')]

    def statistics(self):
        """Hitung konsultasi dan frekuensi aturan sekali per konsultasi."""
        rows = self.history()
        counts = Counter(rid for r in rows for rid in set(t['rule_id'] for t in r['trace']))
        return {'total': len(rows), 'diagnosed': sum(bool(r['diagnoses']) for r in rows), 'rules': dict(sorted(counts.items()))}


def export_txt(result):
    """Ekspor dari snapshot agar perubahan pengetahuan tidak mengubah hasil lama."""
    lines = ['PAKARAC — HASIL KONSULTASI', f"ID: {result['consultation_id']}", f"Waktu: {result['created_at']}", f"Versi pengetahuan: {result['knowledge_version']}", '', 'JAWABAN']
    kb = result['knowledge_snapshot']
    for g in kb['symptoms']:
        a = result['answers'][g['id']]
        lines.append(f"{g['id']} {g['question']} {a['answer']}" + (f" (CF {a['cf']})" if a['answer'] == 'yes' else ''))
    lines += ['', 'HASIL'] + result['alerts']
    for d in result['diagnoses']:
        lines += [f"{d['code']} — {d['name']} ({d['cf']*100:.1f}%)", d['description'], *d['recommendations']]
    if not result['diagnoses']:
        lines.append('Belum ada kesimpulan yang sesuai dengan gejala.')
    lines += ['', 'HOW / JEJAK PENALARAN']
    for t in result['trace']:
        lines.append(f"{t['rule_id']}: IF {' AND '.join(t['if'])} THEN {t['then']}; input={t['inputs']}; CF aturan={t['rule_cf']}; CF hasil={t['cf']:.6f}; {t['combination']}")
    lines += ['', 'SUMBER'] + [f"{s['id']}: {s['name']} — {s['url']}" for s in kb['sources']]
    lines += ['', 'CF adalah dukungan aturan prototipe, bukan akurasi atau kepastian diagnosis. Bobot ditetapkan pengembang; belum divalidasi pakar.']
    return '\n'.join(lines)
