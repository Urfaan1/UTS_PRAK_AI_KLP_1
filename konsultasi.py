"""Form dan hasil konsultasi. Logika inferensi tetap pada mesin_pakar.py."""
from html import escape
import streamlit as st
from mesin_pakar import MesinPakar
from penyimpanan import export_txt


def page_heading(title, subtitle):
    """Judul konsisten di seluruh halaman."""
    st.markdown('<div class="eyebrow">PAKARAC / SISTEM PAKAR</div>',unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<p class="page-sub">{escape(subtitle)}</p>',unsafe_allow_html=True)


def show_result(result, key='current'):
    """Kartu diagnosis, rekomendasi, detail aktual, dan unduhan snapshot."""
    kb=result['knowledge_snapshot']
    for alert in result['alerts']:
        st.error(alert)
    st.caption(f"{result['created_at'][:16].replace('T',' · ')} WIB · Pengetahuan v{result['knowledge_version']}")
    if not result['diagnoses']:
        st.info('Belum cukup bukti untuk menentukan kemungkinan masalah.')
        st.write('Jawab pertanyaan pendukung yang belum diketahui. Jangan menebak kondisi yang belum diperiksa.')
        # Saran bukan diagnosis; hanya aturan yang punya fakta positif dan tidak ditolak fakta negatif.
        facts=set(result['working_memory'])
        suggestions=set()
        for rule in kb['rules']:
            if any(g in facts for g in rule['if']) and not any(result['answers'].get(g,{}).get('answer')=='no' for g in rule['if']):
                suggestions.update(g for g in rule['if'] if result['answers'].get(g,{}).get('answer')=='unknown')
        for g in kb['symptoms']:
            if g['id'] in suggestions:
                st.write('• '+g['question'])
    symptom_labels={g['id']:g['question'] for g in kb['symptoms']}
    for i,d in enumerate(result['diagnoses']):
        st.markdown(f'<div class="result-summary"><div class="small-label">{("Kemungkinan utama" if i==0 else "Kemungkinan lain")} · {escape(d["code"])}</div><h3>{escape(d["name"])}</h3><span class="cf-badge">CF dukungan: {d["cf"]*100:.1f}%</span></div>',unsafe_allow_html=True)
        st.caption('CF adalah dukungan aturan, bukan akurasi diagnosis.')
        st.subheader('Rekomendasi penanganan')
        for j,rec in enumerate(d['recommendations'],1):
            st.markdown(f'<div class="step"><span class="step-no">{j}</span><span>{escape(rec)}</span></div>',unsafe_allow_html=True)
        with st.expander('Gejala pendukung'):
            for gid in d['supporting_symptoms']:
                st.write('• '+symptom_labels.get(gid,gid))
        if i<len(result['diagnoses'])-1:
            st.divider()
    with st.expander('HOW · Lihat proses penalaran'):
        if not result['trace']:
            st.write('Belum ada aturan yang seluruh syaratnya terpenuhi.')
        for t in result['trace']:
            st.markdown(f"**Langkah {t['step']} — {t['rule_id']}**")
            st.code(f"IF {' AND '.join(t['if'])} THEN {t['then']}")
            st.caption(f"CF input {t['inputs']} × CF aturan {t['rule_cf']} → CF hasil {t['cf']:.6f}")
            st.caption(t['combination'])
        st.write('AND: minimum CF syarat × CF aturan. Gabungan: a + b × (1 − a). Bukti asal beririsan tidak digabung.')
        st.markdown('**Working memory**')
        st.json(result['working_memory'])
    with st.expander('Sumber pengetahuan'):
        used={s for d in result['diagnoses'] for s in d['source_ids']}
        for source in kb['sources']:
            if source['id'] in used:
                st.link_button(source['name'],source['url'],width='stretch')
        st.caption('Aturan diadaptasi dari literatur. Bobot CF ditetapkan pengembang dan belum divalidasi pakar.')
    st.download_button('Unduh Hasil TXT',export_txt(result),file_name=f"PakarAC_{result['consultation_id'][:8]}.txt",mime='text/plain',key=f'download_{key}',width='stretch')


def why(kb, symptom_id):
    """Telusuri aturan langsung dan lanjutan untuk menjelaskan pertanyaan."""
    frontier, seen, ids, diagnoses = {symptom_id}, set(), set(), set()
    while frontier:
        fact = frontier.pop()
        if fact in seen:
            continue
        seen.add(fact)
        for rule in kb['rules']:
            if fact in rule['if']:
                ids.add(rule['id'])
                if rule['then'].startswith('K'):
                    diagnoses.add(rule['then'])
                else:
                    frontier.add(rule['then'])
    if not ids:
        return 'Gejala referensi ini belum dipakai oleh aturan aktif.'
    names = [d['name'] for d in kb['diagnoses'] if d['id'] in diagnoses]
    return f"Dipakai pada {', '.join(sorted(ids))} untuk memeriksa: {', '.join(names)}."


def reset_consultation():
    """Bersihkan sesi konsultasi sebelum widget dibuat ulang."""
    for k in list(st.session_state):
        if k.startswith(('answer_','cf_')) or k in ('answers','result','symptom_search','symptom_group'):
            del st.session_state[k]


def render(repo):
    """Dua kolom: angket terarah di kiri, hasil di kanan."""
    page_heading('Konsultasi AC','Jawab pertanyaan sesuai kondisi AC Anda, lalu temukan langkah penanganan awal.')
    st.info('Ini angket konsultasi: pilih Ya, Tidak, atau Tidak tahu. Setelah selesai, klik Diagnosis Sekarang.')
    kb=repo.load()
    answers=st.session_state.setdefault('answers',{g['id']:{'answer':'unknown','cf':None} for g in kb['symptoms']})
    choices={'Ya':'yes','Tidak':'no','Tidak tahu':'unknown'}
    confidence={'Kurang yakin':.4,'Cukup yakin':.6,'Yakin':.8,'Sangat yakin':1.}
    form_col,result_col=st.columns([1.35,1],gap='large')
    with form_col:
        with st.container(border=True):
            st.subheader('Gejala yang dialami')
            groups=list(dict.fromkeys(g['group'] for g in kb['symptoms']))
            group=st.selectbox('Kelompok pertanyaan',groups,key='symptom_group',help='Jawab satu kelompok, lalu pilih kelompok lainnya bila relevan. Jawaban tetap tersimpan.')
            with st.expander('Cari pertanyaan tertentu (opsional)'):
                st.caption('Pencarian hanya menyaring pertanyaan, bukan kolom memasukkan keluhan. Kosongkan untuk melihat semua pertanyaan pada kelompok terpilih.')
                search=st.text_input('Kata kunci pertanyaan',key='symptom_search',placeholder='Contoh: filter, selang, remote').strip().lower()
            if search:
                st.warning('Pencarian aktif. Pertanyaan yang tidak cocok disembunyikan; jawabannya tetap tersimpan.')
                matching=[g for g in kb['symptoms'] if search in (g['id']+' '+g['question']).lower()]
            else:
                matching=[g for g in kb['symptoms'] if g['group']==group]
            if not matching:
                st.info('Tidak ada pertanyaan cocok. Kosongkan kata pencarian.')
            for g in matching:
                gid=g['id']; answer_key='answer_'+gid; cf_key='cf_'+gid
                if answer_key not in st.session_state:
                    st.session_state[answer_key]=next(k for k,v in choices.items() if v==answers[gid]['answer'])
                with st.container(border=True):
                    st.caption(gid+' · '+g['group'])
                    st.markdown('**'+g['question']+'**')
                    left,right=st.columns([1.15,1])
                    with left:
                        label=st.radio('Jawaban '+gid,list(choices),horizontal=True,key=answer_key,label_visibility='collapsed')
                    cf=None
                    if label=='Ya':
                        with right:
                            if cf_key not in st.session_state:
                                st.session_state[cf_key]=next((k for k,v in confidence.items() if v==answers[gid]['cf']),'Yakin')
                            cf=confidence[st.selectbox('Keyakinan pengamatan',list(confidence),key=cf_key,help='Seberapa yakin gejala ini terjadi?')]
                    answers[gid]={'answer':choices[label],'cf':cf}
                    with st.expander('Mengapa ditanyakan?'):
                        st.write(why(kb,gid))
            answered=sum(a['answer']!='unknown' for a in answers.values())
            yes=sum(a['answer']=='yes' for a in answers.values())
            st.caption(f'{answered} dari {len(answers)} pertanyaan dijawab · {yes} gejala Ya. Tidak tahu diperbolehkan.')
            st.progress(answered/len(answers))
            a,b=st.columns([1.4,1])
            diagnose=a.button('Diagnosis Sekarang',type='primary',width='stretch')
            b.button('Reset Jawaban',on_click=reset_consultation,width='stretch')
            st.caption('Periksa hanya bagian yang aman dijangkau. Tidak perlu membongkar unit.')
            if diagnose:
                st.session_state.pop('result',None)
                try:
                    result=MesinPakar(kb).run(answers)
                    repo.save_result(result)
                    st.session_state['result']=result
                except (ValueError,OSError) as exc:
                    st.error(str(exc))
    with result_col:
        with st.container(border=True):
            st.subheader('Hasil Diagnosis')
            if 'result' not in st.session_state:
                st.markdown('<div class="empty-result"><div class="empty-icon">❄</div><h3>Mulai dari gejala AC Anda</h3><p>Jawab pertanyaan di sebelah kiri.<br>Hasil dan rekomendasi akan muncul di sini.</p></div>',unsafe_allow_html=True)
                st.caption('Contoh: kurang dingin + hembusan lemah + filter kotor dapat mendukung aturan masalah filter.')
            else:
                result=st.session_state['result']
                if result['answers']!=answers:
                    st.warning('Jawaban telah berubah. Klik Diagnosis Sekarang untuk memperbarui hasil.')
                if result['knowledge_version']!=kb['version']:
                    st.warning('Aturan telah diperbarui. Jalankan diagnosis lagi untuk memakai versi terbaru.')
                show_result(result)
