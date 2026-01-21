import streamlit as st
import database as db
from datetime import date
import pandas as pd

def painel_monitor():
    user = st.session_state.usuario
    try: st.sidebar.image("logoser.jpg", width=150)
    except: pass
    st.sidebar.markdown(f"## Monitoria")
    st.sidebar.write(f"Olá, {user['nome_completo']}")
    st.sidebar.markdown("---")
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()

    tab_chamada, tab_lista = st.tabs(["✅ Chamada", "👥 Alunos"])
    
    with tab_chamada:
        turmas = db.executar_query("SELECT id, nome FROM turmas WHERE id_filial=%s", (user['id_filial'],), fetch=True)
        d_turmas = {t['nome']: t['id'] for t in turmas} if turmas else {}
        sel = st.selectbox("Turma", list(d_turmas.keys())) if d_turmas else None
        
        if sel:
            id_t = d_turmas[sel]
            alunos = db.executar_query("SELECT id, nome_completo FROM usuarios WHERE id_turma=%s AND status_conta='Ativo' ORDER BY nome_completo", (id_t,), fetch=True)
            with st.form("chamada_mon"):
                checks = []
                for a in alunos:
                    if st.checkbox(a['nome_completo'], key=f"m_{a['id']}"): checks.append(a['id'])
                if st.form_submit_button("Salvar"):
                    db.executar_query("DELETE FROM checkins WHERE id_turma=%s AND data_aula=CURRENT_DATE", (id_t,))
                    for uid in checks: db.executar_query("INSERT INTO checkins (id_aluno, id_turma, id_filial, data_aula) VALUES (%s, %s, %s, CURRENT_DATE)", (uid, id_t, user['id_filial']))
                    st.success("Feito!")
                    
    with tab_lista:
        df = pd.DataFrame(db.executar_query("SELECT nome_completo, faixa FROM usuarios WHERE id_filial=%s AND perfil='aluno'", (user['id_filial'],), fetch=True), columns=['Nome', 'Faixa'])
        st.dataframe(df, use_container_width=True)