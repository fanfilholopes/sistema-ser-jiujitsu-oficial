import streamlit as st
import database as db
import utils
from datetime import date

def painel_aluno():
    user = st.session_state.usuario
    
    # Sidebar
    try: st.sidebar.image("logoser.jpg", width=150)
    except: pass
    st.sidebar.markdown("## Área do Aluno")
    st.sidebar.caption(f"Bem-vindo, {user['nome_completo']}")
    st.sidebar.markdown("---")
    if st.sidebar.button("Sair", key="sair_aluno"):
        st.session_state.logado = False
        st.rerun()

    # Aviso
    aviso = db.executar_query("SELECT mensagem FROM avisos WHERE ativo=TRUE ORDER BY id DESC LIMIT 1", fetch=True)
    if aviso: st.markdown(f"""<div class="aviso-box">📢 {aviso[0]['mensagem']}</div>""", unsafe_allow_html=True)

    # Carteirinha e Stats
    c_card, c_stats = st.columns([1, 2])
    with c_card:
        st.markdown(f"""
        <div class="student-card">
            <h3>{user['nome_completo']}</h3>
            <div class="faixa-tag" style="border-color: {user['faixa']};">{user['faixa']} - {user['graus']}º Grau</div>
            <p style="margin-top:15px; font-size:12px; color:#bbb;">Desde: {user['data_inicio']}</p>
        </div>
        """, unsafe_allow_html=True)

    with c_stats:
        total = db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s", (user['id'],), fetch=True)[0][0]
        presencas_marco = db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s AND data_aula >= %s", (user['id'], user['data_ultimo_grau'] or date.today()), fetch=True)[0][0]
        _, msg_meta, progresso, _ = utils.calcular_status_graduacao(user, presencas_marco)
        
        st.subheader("Minha Jornada 🥋")
        st.progress(progresso)
        st.caption(f"Status: {msg_meta}")
        
        c1, c2 = st.columns(2)
        c1.metric("Total Treinos", total)
        c2.metric("Mês Atual", db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s AND EXTRACT(MONTH FROM data_aula) = EXTRACT(MONTH FROM CURRENT_DATE)", (user['id'],), fetch=True)[0][0])

    st.divider()
    st.subheader("📅 Histórico")
    import pandas as pd
    hist = db.executar_query("SELECT data_aula, 'Presente' as status FROM checkins WHERE id_aluno=%s ORDER BY data_aula DESC LIMIT 10", (user['id'],), fetch=True)
    if hist: st.dataframe(pd.DataFrame(hist, columns=['Data', 'Status']), use_container_width=True)