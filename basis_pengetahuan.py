"""Halaman referensi dan editor aturan, dengan tema Lagoon."""
import copy
from html import escape
import streamlit as st
from konsultasi import why,page_heading


def rule_table(rules, labels):
    """Tabel HTML read-only; seluruh teks data di-escape."""
    header='<tr><th>Kode</th><th>Kondisi IF</th><th>Kesimpulan THEN</th><th>CF</th><th>Sumber</th></tr>'
    rows=[]
    for r in rules:
        conditions=' + '.join(labels.get(a,a) for a in r['if'])
        rows.append(f'<tr><td><b>{escape(r["id"])}</b></td><td>{escape(conditions)}</td><td>{escape(labels.get(r["then"],r["then"]))}</td><td>{r["cf"]:.2f}</td><td>{escape(", ".join(r["source_ids"]))}</td></tr>')
    st.markdown('<div class="rule-table"><table>'+header+''.join(rows)+'</table></div>',unsafe_allow_html=True)


def render(repo):
    """Kelola aturan melalui form, tanpa mengubah algoritma validasi."""
    kb=repo.load()
    page_heading('Basis Pengetahuan','Lihat gejala, kemungkinan masalah, dan aturan yang digunakan sistem.')
    st.markdown(f'<span class="pill">Versi pengetahuan {kb["version"]} · {len(kb["rules"])} aturan</span>',unsafe_allow_html=True)
    st.write('')
    labels={g['id']:g['question'] for g in kb['symptoms']} | kb['intermediates'] | {d['id']:d['name'] for d in kb['diagnoses']}
    td,tg,tr,ts=st.tabs(['Kerusakan','Gejala','Aturan','Sumber'])
    with td:
        with st.container(border=True):
            st.subheader('Kemungkinan masalah AC')
            q=st.text_input('Cari kerusakan',placeholder='Cari nama atau kode masalah...').lower().strip()
            found=[d for d in kb['diagnoses'] if q in (d['id']+' '+d['name']+' '+d['description']).lower()]
            if not found:
                st.info('Tidak ada data yang cocok.')
            for d in found:
                with st.expander(d['id']+' · '+d['name']):
                    st.write(d['description'])
                    st.markdown('**Rekomendasi**')
                    for rec in d['recommendations']:
                        st.write('• '+rec)
                    src={s for r in kb['rules'] if r['then']==d['id'] for s in r['source_ids']}
                    for s in kb['sources']:
                        if s['id'] in src:
                            st.link_button(s['name'],s['url'])
    with tg:
        with st.container(border=True):
            st.subheader('Daftar gejala')
            q=st.text_input('Cari gejala referensi',placeholder='Cari pertanyaan atau kode gejala...').lower().strip()
            st.dataframe([{'Kode':g['id'],'Pertanyaan':g['question'],'Kelompok':g['group'],'WHY':why(kb,g['id'])} for g in kb['symptoms'] if q in (g['id']+' '+g['question']).lower()],hide_index=True,width='stretch')
    with tr:
        st.info('Bobot CF ditetapkan pengembang untuk prototipe. Semua kondisi IF pada satu aturan harus terpenuhi.')
        with st.container(border=True):
            st.subheader('Aturan diagnosis')
            q=st.text_input('Cari aturan',placeholder='Cari kode, gejala, atau kesimpulan...').lower().strip()
            filtered=[r for r in kb['rules'] if q in (' '.join([r['id'],r['then'],*r['if'],*(labels.get(a,a) for a in r['if']),labels.get(r['then'],r['then'])])).lower()]
            rule_table(filtered,labels)
            if not filtered:
                st.caption('Tidak ada aturan yang cocok.')
        with st.container(border=True):
            action=st.radio('Kelola aturan',['Tambah','Edit','Hapus'],horizontal=True,key='rule_action')
            selected=None
            if action!='Tambah':
                if not kb['rules']:
                    st.info('Belum ada aturan untuk diubah.')
                    return
                rid=st.selectbox('Pilih aturan',[r['id'] for r in kb['rules']],format_func=lambda x:x+' — '+labels[next(r['then'] for r in kb['rules'] if r['id']==x)])
                selected=next(r for r in kb['rules'] if r['id']==rid)
            st.subheader(('Tambah Aturan' if selected is None else action+' Aturan '+selected['id']))
            with st.form(f'rule_{action}_{selected["id"] if selected else "new"}_{kb["version"]}'):
                if action=='Hapus':
                    st.warning('Aturan dihapus untuk konsultasi berikutnya. Riwayat lama tetap menyimpan salinan aturan.')
                    st.code('IF '+' AND '.join(selected['if'])+' THEN '+selected['then'])
                    confirmed=st.checkbox('Saya ingin menghapus aturan ini')
                else:
                    c1,c2=st.columns([1,2])
                    rid=c1.text_input('Kode aturan',value=selected['id'] if selected else '',placeholder='Contoh: R16',disabled=selected is not None)
                    ant=c2.multiselect('IF · pilih gejala / fakta sementara',[g['id'] for g in kb['symptoms']]+list(kb['intermediates']),default=selected['if'] if selected else [],format_func=lambda x:f'{x} — {labels[x]}')
                    targets=list(kb['intermediates'])+[d['id'] for d in kb['diagnoses']]
                    target=st.selectbox('THEN · pilih kesimpulan',targets,index=targets.index(selected['then']) if selected else 0,format_func=lambda x:f'{x} — {labels[x]}')
                    c1,c2=st.columns([1,2])
                    cf=c1.number_input('CF aturan',min_value=.01,max_value=1.,value=float(selected['cf']) if selected else .8,step=.05)
                    src=c2.multiselect('Sumber pengetahuan',[s['id'] for s in kb['sources']],default=selected['source_ids'] if selected else [],format_func=lambda x:next(s['id']+' — '+s['name'] for s in kb['sources'] if s['id']==x))
                submitted=st.form_submit_button('Hapus Aturan' if action=='Hapus' else 'Simpan Perubahan',type='primary')
            if submitted:
                try:
                    rules=copy.deepcopy(kb['rules'])
                    if action=='Hapus':
                        if not confirmed:
                            raise ValueError('Centang konfirmasi penghapusan terlebih dahulu.')
                        rules=[r for r in rules if r['id']!=selected['id']]
                    else:
                        item={'id':rid.strip().upper(),'if':ant,'then':target,'cf':cf,'source_ids':src,'cf_basis':'developer_assigned','validation_status':'literature_based_prototype'}
                        if action=='Tambah':
                            rules.append(item)
                        else:
                            rules=[item if r['id']==selected['id'] else r for r in rules]
                    repo.save_rules(rules,kb['version'])
                    st.session_state['knowledge_notice']='Perubahan aturan berhasil disimpan.'
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        if 'knowledge_notice' in st.session_state:
            st.success(st.session_state.pop('knowledge_notice'))
    with ts:
        st.info('Panduan produsen mendukung hubungan gejala dan tindakan awal. Angka CF adalah rancangan pengembang, bukan angka dari produsen. Sistem tidak menafsirkan kode error lintas model.')
        for s in kb['sources']:
            with st.container(border=True):
                st.markdown('**'+s['id']+' · '+s['name']+'**')
                st.caption(s['url'])
                st.link_button('Buka sumber',s['url'])
