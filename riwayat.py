"""Riwayat dua kolom: daftar tersaring dan detail snapshot."""
from datetime import date
from html import escape
import streamlit as st
from konsultasi import show_result,page_heading


def render(repo):
    """Statistik, filter, detail dan ekspor; tidak membuat konsultasi baru."""
    page_heading('Riwayat Konsultasi','Lihat kembali hasil pemeriksaan dan rekomendasi untuk AC Anda.')
    stats=repo.statistics()
    a,b,c=st.columns(3)
    a.metric('Total konsultasi',stats['total'])
    b.metric('Dengan hasil',stats['diagnosed'])
    c.metric('Tanpa hasil',stats['total']-stats['diagnosed'])
    st.write('')
    rows=repo.history()
    if not rows:
        with st.container(border=True):
            st.markdown('<div class="empty-result"><div class="empty-icon">◷</div><h3>Riwayat Anda masih kosong</h3><p>Jalankan diagnosis di menu Konsultasi AC.<br>Hasilnya akan tersimpan otomatis di sini.</p></div>',unsafe_allow_html=True)
        return
    dates=[date.fromisoformat(r['created_at'][:10]) for r in rows]
    with st.container(border=True):
        a,b,c,d=st.columns(4)
        start=a.date_input('Dari tanggal',min(dates))
        end=b.date_input('Sampai tanggal',max(dates))
        names=sorted({x['name'] for r in rows for x in r['diagnoses']})
        diagnosis=c.selectbox('Diagnosis',['Semua']+names)
        status=d.selectbox('Status',['Semua','Dengan hasil','Tanpa hasil'])
        q=st.text_input('Cari konsultasi',placeholder='Cari ID, diagnosis, atau gejala yang dijawab Ya...').lower().strip()
    if start>end:
        st.warning('Tanggal awal harus sebelum atau sama dengan tanggal akhir.')
    filtered=[]
    for r in rows:
        symptoms=[g['question'] for g in r['knowledge_snapshot']['symptoms'] if r['answers'][g['id']]['answer']=='yes']
        haystack=' '.join([r['consultation_id']]+[d['name'] for d in r['diagnoses']]+symptoms).lower()
        if not start<=date.fromisoformat(r['created_at'][:10])<=end:
            continue
        if (status=='Dengan hasil' and not r['diagnoses']) or (status=='Tanpa hasil' and r['diagnoses']):
            continue
        if diagnosis!='Semua' and not any(d['name']==diagnosis for d in r['diagnoses']):
            continue
        if q not in haystack:
            continue
        filtered.append(r)
    st.write('')
    left,right=st.columns([1.2,1],gap='large')
    with left:
        with st.container(border=True):
            st.subheader('Daftar konsultasi')
            st.caption(f'{len(filtered)} konsultasi sesuai filter')
            if filtered:
                options=[r['consultation_id'] for r in filtered]
                # Tetap mempertahankan pilihan bila filter yang berubah masih memuat ID ini.
                if st.session_state.get('history_selected') not in options:
                    st.session_state['history_selected']=options[0]
                selected=st.selectbox('Pilih untuk melihat detail',options,key='history_selected',format_func=lambda x:next(r['created_at'][:16].replace('T',' · ')+' WIB — '+x[:8] for r in filtered if r['consultation_id']==x))
                body=''
                for r in filtered:
                    name=', '.join(d['name'] for d in r['diagnoses']) or 'Belum ada kesimpulan'
                    cls=' class="selected"' if r['consultation_id']==selected else ''
                    body+=f'<tr{cls}><td>{escape(r["consultation_id"][:8])}</td><td>{escape(r["created_at"][:16].replace("T"," "))}</td><td>{escape(name)}</td></tr>'
                st.markdown('<div class="rule-table"><table><tr><th>ID</th><th>Waktu (WIB)</th><th>Hasil</th></tr>'+body+'</table></div>',unsafe_allow_html=True)
            else:
                selected=None
                st.info('Tidak ada konsultasi sesuai filter. Ubah tanggal, kata pencarian, atau pilihan filter.')
        with st.container(border=True):
            st.subheader('Aturan yang sering digunakan')
            st.caption('Seluruh riwayat · maksimal satu hitungan per aturan per konsultasi')
            st.dataframe([{'Aturan':rid,'Konsultasi':n} for rid,n in sorted(stats['rules'].items(),key=lambda x:(-x[1],x[0]))],hide_index=True,width='stretch')
    with right:
        with st.container(border=True):
            st.subheader('Detail konsultasi')
            if selected:
                show_result(next(r for r in filtered if r['consultation_id']==selected),key='history_'+selected)
            else:
                st.caption('Pilih konsultasi dari daftar untuk melihat detail dan mengunduh hasil.')
