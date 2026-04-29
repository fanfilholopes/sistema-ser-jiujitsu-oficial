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
        menu_monitoria = st.radio("Selecione a ação", ["✅ Chamada", "➕ Matrícula", "🎂 Aniversariantes"], horizontal=True, label_visibility="collapsed")
        st.divider()

        # --- CHAMADA DA TURMA ---
        if menu_monitoria == "✅ Chamada":
            st.markdown("### 📋 Realizar Chamada")
            data_aula = st.date_input("Data da Aula", value=date.today())
            
            alunos = db.executar_query("""
                SELECT id, nome_completo, faixa, graus FROM usuarios 
                WHERE id_turma=%s AND status_conta='Ativo' 
                ORDER BY nome_completo
            """, (mt['id'],), fetch=True)
            
            # Otimização: Verifica presenças em lote para o dia selecionado
            res_presencas = db.executar_query("SELECT id_aluno FROM checkins WHERE id_turma=%s AND data_aula=%s AND validado=TRUE", (mt['id'], data_aula), fetch=True)
            presencas_hoje = [x[0] for x in res_presencas] if res_presencas else []
            
            with st.form("chamada_monitor"):
                checks = []
                if alunos:
                    c_al = st.columns(2)
                    for i, a in enumerate(alunos):
                        with c_al[i % 2]:
                            ja_marcado = a['id'] in presencas_hoje
                            if st.checkbox(f"{a['nome_completo']} ({a['faixa']})", value=ja_marcado, key=f"mon_ch_{a['id']}"):
                                checks.append(a['id'])
                else:
                    st.caption("Nenhum aluno matriculado nesta turma.")
                
                if st.form_submit_button("💾 Salvar Chamada Oficial", type="primary", use_container_width=True):
                    # Limpa as presenças do dia para esta turma para evitar duplicidade
                    db.executar_query("DELETE FROM checkins WHERE id_turma=%s AND data_aula=%s", (mt['id'], data_aula))
                    
                    for uid in checks:
                        db.executar_query("""
                            INSERT INTO checkins (id_aluno, id_turma, id_filial, data_aula, validado) 
                            VALUES (%s, %s, %s, %s, TRUE)
                        """, (uid, mt['id'], id_filial, data_aula))
                    
                    st.success(f"Chamada de {len(checks)} alunos salva!")
                    time.sleep(1)
                    st.rerun()

        # --- MATRÍCULA PELO MONITOR ---
        elif menu_monitoria == "➕ Matrícula":
            st.markdown("### 📝 Nova Matrícula")
            st.info("ℹ️ O cadastro ficará **Pendente** para aprovação do Admin da Filial.")
            
            nasc = st.date_input("Data de Nascimento", value=date(2015, 1, 1))
            idade = utils.calcular_idade_ano(nasc)
            is_kid = idade < 16

            with st.form("form_matricula_monitor"):
                c1, c2 = st.columns([2, 1])
                nome = c1.text_input("Nome Completo")
                email = c2.text_input("E-mail (Login)").strip().lower()
                
                st.markdown("##### 🥋 Dados Técnicos")
                c5, c6 = st.columns(2)
                faixa = c5.selectbox("Faixa", utils.ORDEM_FAIXAS)
                graus = c6.selectbox("Graus Atuais", [0, 1, 2, 3, 4])
                
                nm_resp = None
                if is_kid:
                    st.warning(f"👶 Aluno Kids ({idade} anos)")
                    nm_resp = st.text_input("Nome do Responsável")
                
                if st.form_submit_button("🚀 Enviar Matrícula", type="primary", use_container_width=True):
                    if not nome or not email:
                        st.error("Preencha o Nome e E-mail.")
                    elif is_kid and not nm_resp:
                        st.error("Nome do responsável é obrigatório.")
                    else:
                        res = db.executar_query("""
                            INSERT INTO usuarios 
                            (nome_completo, email, senha, data_nascimento, faixa, graus, 
                            id_filial, id_turma, perfil, status_conta, data_inicio, 
                            data_ultimo_grau, nome_responsavel) 
                            VALUES (%s, %s, '123', %s, %s, %s, %s, %s, 'aluno', 'Pendente', CURRENT_DATE, CURRENT_DATE, %s)
                            RETURNING id
                        """, (nome, email, nasc, faixa, graus, id_filial, mt['id'], nm_resp), fetch=True)
                        
                        if res == "ERRO_DUPLICADO":
                            st.error("E-mail já cadastrado.")
                        elif res:
                            # Registra histórico inicial para evitar ficha vazia
                            novo_id = res[0]['id']
                            db.executar_query("""
                                INSERT INTO historico_graduacoes (id_aluno, faixa, grau, data_graduacao) 
                                VALUES (%s, %s, %s, CURRENT_DATE)
                            """, (novo_id, faixa, graus))
                            
                            st.success("Matrícula enviada para aprovação do Admin!")
                            time.sleep(1.5)
                            st.rerun()

        # --- ANIVERSARIANTES ---
        elif menu_monitoria == "🎂 Aniversariantes":
            st.markdown("### 🎉 Aniversariantes do Mês")
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
                st.info("Sem aniversariantes na turma este mês.")

    # =======================================================
    # MODO 2: VISÃO DE ALUNO
    # =======================================================
    elif modo == "Minha Área de Aluno":
        # Chamamos a função do aluno_view passando False para não duplicar a sidebar
        aluno_view.painel_aluno(renderizar_sidebar=False)