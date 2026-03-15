import streamlit as st
import database as db
import utils
import pandas as pd
from datetime import date
import time
import views.aluno as aluno_view

def painel_monitor():
    user = st.session_state.usuario
    id_monitor = user['id']
    id_filial = user['id_filial']
    perfil = user.get('perfil', 'monitor')

    # Busca a turma que ele monitora
    minha_turma_monitoria = db.executar_query("SELECT id, nome, horario, dias FROM turmas WHERE id_monitor=%s", (id_monitor,), fetch=True)

    # =======================================================
    # --- SIDEBAR PADRONIZADA ---
    # =======================================================
    try: 
        st.sidebar.image("logoser.jpg", width=150)
    except: 
        pass

    st.sidebar.markdown("## Painel Monitor")
    st.sidebar.caption(f"Olá, {user['nome_completo']}")
    
    if minha_turma_monitoria:
        mt_badge = minha_turma_monitoria[0]
        st.sidebar.success(f"🧢 Monitor da: **{mt_badge['nome']}**")

    st.sidebar.markdown("---")
    
    # --- MODO DE VISÃO ---
    st.sidebar.markdown("### 🔭 Navegação")
    modo = st.sidebar.radio("Navegação", ["🧢 Área da Monitoria", "🥋 Minha Área de Aluno"], label_visibility="collapsed")

    st.sidebar.markdown("---")
    
    if st.sidebar.button("Sair", use_container_width=True):
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

        mt = minha_turma_monitoria[0]
        st.title(f"Gestão: {mt['nome']}")
        st.caption(f"Horário: {mt['horario']} | Dias: {mt['dias']}")
        
        # --- MENU HORIZONTAL ---
        menu_monitoria = st.radio("Selecione a ação", ["✅ Chamada", "➕ Matrícula Completa", "🎂 Aniversariantes"], horizontal=True, label_visibility="collapsed")
        st.divider()

        # --- CHAMADA DA TURMA ---
        if menu_monitoria == "✅ Chamada":
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

        # --- MATRÍCULA COMPLETA PELO MONITOR ---
        elif menu_monitoria == "➕ Matrícula Completa":
            st.markdown("### 📝 Nova Matrícula Completa")
            st.info("ℹ️ O cadastro ficará **Pendente** para aprovação exclusiva do **Admin da Filial**.")
            
            # Escolha da Data de Nascimento antes do formulário para lógica Kids
            nasc = st.date_input("Data de Nascimento", value=date(2010, 1, 1))
            idade = (date.today() - nasc).days // 365
            is_kid = idade < 16

            with st.form("form_matricula_completa_monitor"):
                c1, c2 = st.columns([2, 1])
                nome = c1.text_input("Nome Completo")
                email = c2.text_input("E-mail (Login)")
                
                c3, c4 = st.columns(2)
                zap = c3.text_input("WhatsApp Aluno")
                zap_resp = "" # Inicializa para não dar erro
                
                st.markdown("---")
                st.markdown("##### 🥋 Dados Técnicos")
                c5, c6, c7 = st.columns(3)
                faixa = c5.selectbox("Faixa", utils.ORDEM_FAIXAS)
                graus = c6.selectbox("Graus", [0, 1, 2, 3, 4])
                dt_inicio = c7.date_input("Data de Início", value=date.today())

                c8, c9 = st.columns(2)
                dt_faixa = c8.date_input("Data da Faixa Atual", value=date.today())
                dt_ult_grau = c9.date_input("Data do Último Grau", value=date.today())

                nm_resp, tel_resp = None, None
                if is_kid:
                    st.markdown("---")
                    st.warning(f"👶 Aluno Menor ({idade} anos). Dados do Responsável:")
                    cr1, cr2 = st.columns(2)
                    nm_resp = cr1.text_input("Nome do Responsável")
                    tel_resp = cr2.text_input("WhatsApp do Responsável")
                
                st.write("")
                if st.form_submit_button("🚀 Finalizar Matrícula e Enviar para Admin", type="primary", use_container_width=True):
                    if not nome or not email:
                        st.error("Campos Nome e E-mail são obrigatórios.")
                    elif is_kid and not nm_resp:
                        st.error("Nome do responsável é obrigatório para menores.")
                    else:
                        # Define qual data de graduação salvar
                        data_grad_final = dt_ult_grau if graus > 0 else dt_faixa
                        
                        res = db.executar_query("""
                            INSERT INTO usuarios 
                            (nome_completo, email, senha, telefone, data_nascimento, faixa, graus, 
                            id_filial, id_turma, perfil, status_conta, data_inicio, 
                            data_graduacao, data_ultimo_grau, nome_responsavel, telefone_responsavel) 
                            VALUES (%s, %s, '123', %s, %s, %s, %s, %s, %s, 'aluno', 'Pendente', %s, %s, %s, %s, %s)
                        """, (nome, email, zap, nasc, faixa, graus, id_filial, mt['id'], dt_inicio, dt_faixa, data_grad_final, nm_resp, tel_resp))
                        
                        if res == "ERRO_DUPLICADO":
                            st.error("Este e-mail já está em uso.")
                        elif res:
                            st.success("✅ Matrícula enviada! O Admin da Filial recebeu a notificação para aprovação.")
                            time.sleep(2)
                            st.rerun()

        # --- ANIVERSARIANTES ---
        elif menu_monitoria == "🎂 Aniversariantes":
            st.markdown("### 🎉 Aniversariantes do Mês (Turma)")
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
            else: 
                st.info("Sem aniversariantes nesta turma para o mês atual.")

    # =======================================================
    # MODO 2: VISÃO DE ALUNO
    # =======================================================
    elif modo == "Minha Área de Aluno":
        aluno_view.painel_aluno(renderizar_sidebar=False)