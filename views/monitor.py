import streamlit as st
import database as db
import utils
import pandas as pd
from datetime import date
import time
import views.aluno as aluno_view # Importação correta

def painel_monitor():
    user = st.session_state.usuario
    id_monitor = user['id']
    id_filial = user['id_filial']

    # --- SIDEBAR ---
    try: st.sidebar.image("logoser.jpg", width=150)
    except: pass
    
    st.sidebar.title("Painel Monitor")
    st.sidebar.caption(f"Olá, {user['nome_completo']}")
    
    # Busca a turma que ele monitora
    minha_turma_monitoria = db.executar_query("SELECT id, nome, horario, dias FROM turmas WHERE id_monitor=%s", (id_monitor,), fetch=True)
    
    if minha_turma_monitoria:
        mt = minha_turma_monitoria[0]
        st.sidebar.success(f"🧢 Monitor da: **{mt['nome']}**")
    
    st.sidebar.markdown("---")
    modo = st.sidebar.radio("Navegação", ["🧢 Área da Monitoria", "🥋 Minha Área de Aluno"])

    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()

    # =======================================================
    # MODO 1: ÁREA DA MONITORIA (Gestão)
    # =======================================================
    if modo == "🧢 Área da Monitoria":
        if not minha_turma_monitoria:
            st.warning("⚠️ Você ainda não foi vinculado a nenhuma turma como Monitor.")
            st.info("Peça para o Professor ou Admin editar a turma e selecionar seu nome no campo 'Monitor'.")
            return

        st.title(f"Gestão: {mt['nome']}")
        st.caption(f"Horário: {mt['horario']} | Dias: {mt['dias']}")
        
        tab_chamada, tab_niver = st.tabs(["✅ Chamada da Turma", "🎂 Aniversariantes"])

        # --- CHAMADA DA TURMA ---
        with tab_chamada:
            st.markdown("### 📋 Realizar Chamada")
            data_aula = st.date_input("Data da Aula", value=date.today())
            
            alunos = db.executar_query("""
                SELECT id, nome_completo, faixa FROM usuarios 
                WHERE id_turma=%s AND status_conta='Ativo' 
                ORDER BY nome_completo
            """, (mt['id'],), fetch=True)
            
            checkins_feitos = [x[0] for x in db.executar_query("SELECT id_aluno FROM checkins WHERE id_turma=%s AND data_aula=%s", (mt['id'], data_aula), fetch=True)]
            
            with st.form("chamada_monitor"):
                checks = []
                cols = st.columns(2)
                if alunos:
                    for i, a in enumerate(alunos):
                        with cols[i % 2]:
                            ja_marcado = a['id'] in checkins_feitos
                            if st.checkbox(f"{a['nome_completo']} ({a['faixa']})", value=ja_marcado, key=f"mon_ch_{a['id']}"):
                                checks.append(a['id'])
                else:
                    st.caption("Nenhum aluno matriculado nesta turma.")
                
                st.write("")
                if st.form_submit_button("💾 Salvar Chamada", type="primary", use_container_width=True):
                    db.executar_query("DELETE FROM checkins WHERE id_turma=%s AND data_aula=%s", (mt['id'], data_aula))
                    for uid in checks:
                        db.executar_query("INSERT INTO checkins (id_aluno, id_turma, id_filial, data_aula, validado) VALUES (%s, %s, %s, %s, TRUE)", (uid, mt['id'], id_filial, data_aula))
                    st.success("Chamada realizada com sucesso!"); time.sleep(1); st.rerun()

        # --- ANIVERSARIANTES ---
        with tab_niver:
            st.markdown("### 🎉 Próximos Aniversariantes")
            niver = db.executar_query("""
                SELECT nome_completo, TO_CHAR(data_nascimento, 'DD/MM') as dia 
                FROM usuarios 
                WHERE id_turma=%s AND status_conta='Ativo'
                AND EXTRACT(MONTH FROM data_nascimento) = EXTRACT(MONTH FROM CURRENT_DATE)
                ORDER BY EXTRACT(DAY FROM data_nascimento)
            """, (mt['id'],), fetch=True)
            
            if niver:
                for n in niver:
                    st.success(f"🎈 **{n['dia']}** - {n['nome_completo']}")
            else: st.info("Nenhum aniversariante nesta turma este mês.")

    # =======================================================
    # MODO 2: VISÃO DE ALUNO (Reutilizando código!)
    # =======================================================
    elif modo == "🥋 Minha Área de Aluno":
        # Chama a função do arquivo aluno.py SEM renderizar a sidebar duplicada
        aluno_view.painel_aluno(renderizar_sidebar=False)