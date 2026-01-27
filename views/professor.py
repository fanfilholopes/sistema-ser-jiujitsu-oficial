import streamlit as st
import database as db
import utils
import pandas as pd
from datetime import date
import time

def painel_professor():
    user = st.session_state.usuario
    id_filial = user['id_filial']
    id_prof = user['id']

    # --- SIDEBAR SIMPLES ---
    try: st.sidebar.image("logoser.jpg", width=150)
    except: pass
    st.sidebar.title("Área do Professor 🥋")
    st.sidebar.caption(f"Olá, {user['nome_completo']}")
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()

    # --- ABA ÚNICA: GESTÃO DE AULAS ---
    st.title("🛡️ Gestão de Tatame")
    
    # 1. VALIDAÇÃO DE CHECK-INS (O ACEITE)
    st.subheader("🔔 Check-ins Pendentes de Aceite")
    
    # Busca check-ins de HOJE que ainda NÃO foram validados (validado=FALSE)
    # Filtra apenas turmas deste professor (ou todas da filial se for admin vendo)
    pendencias = db.executar_query("""
        SELECT c.id, u.nome_completo, t.nome as turma, t.horario 
        FROM checkins c
        JOIN usuarios u ON c.id_aluno = u.id
        JOIN turmas t ON c.id_turma = t.id
        WHERE c.id_filial=%s 
        AND c.data_aula = CURRENT_DATE 
        AND c.validado = FALSE
        AND (t.id_professor = %s OR %s IS NULL) -- Mostra turmas do prof ou todas se ele não tiver turma
        ORDER BY t.horario
    """, (id_filial, id_prof, None), fetch=True) 
    # Obs: Ajustei a query para ser generosa. Se quiser restringir só às turmas DELE, tire o "OR %s IS NULL".

    if pendencias:
        st.info(f"Você tem {len(pendencias)} alunos aguardando liberação para o treino.")
        
        # Cria uma "mesa de aprovação"
        for p in pendencias:
            with st.container(border=True):
                c_info, c_btn = st.columns([3, 1])
                c_info.markdown(f"**{p['nome_completo']}**")
                c_info.caption(f"Turma: {p['turma']} às {p['horario']}")
                
                col_ok, col_no = c_btn.columns(2)
                if col_ok.button("✅", key=f"ok_{p['id']}", help="Aceitar Presença"):
                    db.executar_query("UPDATE checkins SET validado=TRUE WHERE id=%s", (p['id'],))
                    st.toast(f"{p['nome_completo']} confirmado!"); time.sleep(0.5); st.rerun()
                
                if col_no.button("❌", key=f"no_{p['id']}", help="Recusar (Aluno não veio)"):
                    db.executar_query("DELETE FROM checkins WHERE id=%s", (p['id'],))
                    st.toast("Check-in recusado."); time.sleep(0.5); st.rerun()
    else:
        st.success("Tudo limpo! Nenhum check-in pendente agora.")

    st.divider()

    # 2. LISTA DE PRESENÇA JÁ VALIDADA (Só para conferência)
    st.subheader("✅ Confirmados no Tatame Hoje")
    confirmados = db.executar_query("""
        SELECT u.nome_completo, t.nome as turma, u.faixa 
        FROM checkins c
        JOIN usuarios u ON c.id_aluno = u.id
        JOIN turmas t ON c.id_turma = t.id
        WHERE c.id_filial=%s AND c.data_aula = CURRENT_DATE AND c.validado = TRUE
        ORDER BY t.horario DESC
    """, (id_filial,), fetch=True)
    
    if confirmados:
        for c in confirmados:
            st.markdown(f"- **{c['nome_completo']}** ({c['faixa']}) <span style='color:grey'>| {c['turma']}</span>", unsafe_allow_html=True)
    else:
        st.caption("Nenhum aluno confirmado ainda.")