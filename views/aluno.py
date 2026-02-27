import streamlit as st
import database as db
import utils
import pandas as pd
from datetime import date
import time

def painel_aluno(renderizar_sidebar=True):
    user = st.session_state.usuario
    
    # --- CORES DAS FAIXAS (Local) ---
    CORES_FAIXAS = {
        'Branca': '#F0F0F0', 'Cinza': '#A0A0A0', 'Amarela': '#FFD700',
        'Laranja': '#FF8C00', 'Verde': '#228B22', 'Azul': '#0000FF',
        'Roxa': '#800080', 'Marrom': '#8B4513', 'Preta': '#000000'
    }

    # --- BUSCAR DADOS EXTRAS ---
    filial_data = db.executar_query("SELECT nome FROM filiais WHERE id=%s", (user['id_filial'],), fetch=True)
    nome_filial = filial_data[0]['nome'] if filial_data else "Matriz / Sede"

    nome_turma = "Não enturmado"
    detalhes_turma = ""
    if user['id_turma']:
        turma_data = db.executar_query("SELECT nome, dias, horario FROM turmas WHERE id=%s", (user['id_turma'],), fetch=True)
        if turma_data:
            t = turma_data[0]
            nome_turma = t['nome']
            detalhes_turma = f"{t['dias']} às {t['horario']}"

    # =======================================================
    # --- SIDEBAR PADRONIZADA (Só renderiza se for Aluno puro) ---
    # =======================================================
    if renderizar_sidebar:
        try: 
            st.sidebar.image("logoser.jpg", width=150)
        except: 
            pass

        st.sidebar.markdown("## Área do Aluno")
        st.sidebar.caption(f"Olá, {user['nome_completo']}")
        
        st.sidebar.markdown(f"📍 **{nome_filial}**")
        st.sidebar.markdown(f"🥋 **{user['faixa']}** ({user['graus']}º Grau)")
        
        st.sidebar.markdown("---")
        
        # 3. NAVEGAÇÃO OTIMIZADA
        st.sidebar.markdown("### 📌 Menu")
        menu_selecionado = st.sidebar.radio(
            "Navegação", 
            ["🏠 Meu Tatame", "📜 Histórico", "🏅 Competições"], 
            label_visibility="collapsed"
        )

        st.sidebar.markdown("---")
        if st.sidebar.button("Sair", key="sair_aluno"):
            st.session_state.logado = False
            st.rerun()

    else:
        # Quando chamado pelo monitor.py, renderiza um menu horizontal limpo no topo
        menu_selecionado = st.radio(
            "Navegação do Aluno", 
            ["🏠 Meu Tatame", "📜 Histórico", "🏅 Competições"], 
            horizontal=True,
            label_visibility="collapsed"
        )
        st.divider()


    # =======================================================
    # CONTEÚDO PRINCIPAL (Alta Performance)
    # =======================================================
    
    if menu_selecionado == "🏠 Meu Tatame":
        # --- RANKING CURIOSIDADE ---
        sql_rank = """
            SELECT id_aluno, COUNT(*) as qtd 
            FROM checkins 
            WHERE id_filial=%s AND validado=TRUE 
            AND EXTRACT(YEAR FROM data_aula) = %s 
            GROUP BY id_aluno 
            ORDER BY qtd DESC
        """
        ranking_geral = db.executar_query(sql_rank, (user['id_filial'], date.today().year), fetch=True)
        
        posicao = "-"
        if ranking_geral:
            for idx, r in enumerate(ranking_geral):
                if r['id_aluno'] == user['id']:
                    posicao = f"{idx + 1}º"
                    break
        
        c_rank, c_msg = st.columns([1, 2])
        c_rank.metric("🏆 Ranking Anual", posicao, delta="Casca Grossa", delta_color="off")
        c_msg.info("Treine com constância para subir no ranking da equipe!")
        st.divider()

        # --- LÓGICA DO STATUS DO CHECK-IN ---
        dados_checkin = db.executar_query("SELECT validado FROM checkins WHERE id_aluno=%s AND data_aula=CURRENT_DATE", (user['id'],), fetch=True)
        fez_checkin = False
        esta_validado = False
        if dados_checkin:
            fez_checkin = True
            esta_validado = dados_checkin[0][0]

        # Verifica solicitações de graduação
        solicitacao = db.executar_query("""
            SELECT nova_faixa, status FROM solicitacoes_graduacao 
            WHERE id_aluno=%s AND status != 'Concluido' 
            ORDER BY id DESC LIMIT 1
        """, (user['id'],), fetch=True)

        c_check, c_aviso_grad = st.columns([1, 2])

        with c_check:
            st.markdown("##### 📍 Presença Hoje")
            if fez_checkin:
                if esta_validado: st.success("✅ Confirmada!")
                else:
                    st.warning("⏳ Aguardando Prof.")
                    st.caption("O professor precisa aceitar seu check-in.")
            else:
                if st.button("📲 Fazer Check-in", type="primary", use_container_width=True):
                    if user['id_turma']:
                        db.executar_query("""
                            INSERT INTO checkins (id_aluno, id_turma, id_filial, data_aula, validado) 
                            VALUES (%s, %s, %s, CURRENT_DATE, FALSE)
                        """, (user['id'], user['id_turma'], user['id_filial']))
                        st.toast("Solicitação enviada ao professor!"); time.sleep(1.5); st.rerun()
                    else: st.error("Você não está em uma turma. Fale com seu professor.")

        with c_aviso_grad:
            if solicitacao:
                sol = solicitacao[0]
                status_map = {
                    'Pendente': '🟡 Aguardando Aprovação',
                    'Aguardando Exame': '🥋 Aprovado! Prepare-se para o Exame.',
                    'Aguardando Homologacao': '🎓 Exame Concluído! Aguardando Faixa.'
                }
                msg_status = status_map.get(sol['status'], sol['status'])
                st.info(f"🎉 **Parabéns!** Indicado para **{sol['nova_faixa']}**.\n\n**Status:** {msg_status}")

        st.divider()

        # --- MURAL DE AVISOS ---
        avisos = db.executar_query("""
            SELECT titulo, mensagem, data_postagem FROM avisos 
            WHERE ativo=TRUE AND publico_alvo IN ('Todos', 'Alunos') 
            ORDER BY id DESC
        """, fetch=True)
        
        if avisos: 
            st.markdown("### 📢 Avisos")
            for av in avisos:
                with st.container(border=True):
                    st.markdown(f"**{av['titulo']}** <small style='color:grey'>({av['data_postagem'].strftime('%d/%m')})</small>", unsafe_allow_html=True)
                    st.write(av['mensagem'])
            st.divider()

        # --- ESTATÍSTICAS E CARTEIRINHA ---
        c_card, c_stats = st.columns([1.2, 1.8])
        
        with c_card:
            cor_faixa = CORES_FAIXAS.get(user['faixa'], '#ccc')
            cor_texto_tag = 'black' if user['faixa'] in ['Branca', 'Amarela'] else 'white'

            html_card = f"""
    <div style="background-color: #1E1E1E; padding: 20px; border-radius: 12px; border-left: 6px solid {cor_faixa}; box-shadow: 0 4px 10px rgba(0,0,0,0.4);">
    <small style="color:#888; text-transform:uppercase; letter-spacing:1px;">Aluno Oficial</small>
    <h3 style="margin:5px 0 0 0; color:white;">{user['nome_completo']}</h3>
    <p style="margin:0 0 15px 0; color:#aaa; font-size:0.9em;">{user['email']}</p>
    <div style="display:flex; gap:10px; align-items:center; margin-bottom:15px;">
    <div style="background-color: {cor_faixa}; color: {cor_texto_tag}; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size:0.9em;">
    {user['faixa']} {user['graus']}º
    </div>
    <div style="color:#ccc; font-size:0.9em;">
    📍 {nome_filial}
    </div>
    </div>
    <div style="background-color:#2b2b2b; padding:10px; border-radius:8px;">
    <p style="margin:0; color:#888; font-size:0.8em;">TURMA ATUAL</p>
    <p style="margin:2px 0 0 0; color:white; font-weight:500;">{nome_turma}</p>
    <p style="margin:0; color:#aaa; font-size:0.8em;">{detalhes_turma}</p>
    </div>
    <p style="margin-top:15px; font-size:10px; color:#666; text-align:right;">Desde: {user['data_inicio']}</p>
    </div>
    """
            st.markdown(html_card, unsafe_allow_html=True)

        with c_stats:
            total = db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s AND validado=TRUE", (user['id'],), fetch=True)[0][0]
            presencas_marco = db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s AND validado=TRUE AND data_aula >= %s", (user['id'], user['data_ultimo_grau'] or date.today()), fetch=True)[0][0]
            _, msg_meta, progresso, _ = utils.calcular_status_graduacao(user, presencas_marco)
            
            st.subheader("Minha Jornada 🥋")
            st.progress(progresso)
            st.caption(f"Status para próximo grau: {msg_meta}")
            
            k1, k2 = st.columns(2)
            k1.metric("Treinos (Total)", total)
            k2.metric("Treinos (Este Mês)", db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s AND validado=TRUE AND EXTRACT(MONTH FROM data_aula) = EXTRACT(MONTH FROM CURRENT_DATE)", (user['id'],), fetch=True)[0][0])

    elif menu_selecionado == "📜 Histórico":
        st.markdown("### 📅 Meus Treinos")
        with st.expander("📅 Ver Histórico de Presença", expanded=True):
            hist = db.executar_query("SELECT data_aula, 'Presente' as status FROM checkins WHERE id_aluno=%s AND validado=TRUE ORDER BY data_aula DESC LIMIT 10", (user['id'],), fetch=True)
            if hist: 
                df_hist = pd.DataFrame(hist, columns=['Data do Treino', 'Status'])
                df_hist['Data do Treino'] = pd.to_datetime(df_hist['Data do Treino']).dt.strftime('%d/%m/%Y')
                st.dataframe(df_hist, use_container_width=True, hide_index=True)
            else: st.info("Nenhum treino validado registrado ainda.")

    elif menu_selecionado == "🏅 Competições":
        st.markdown("### 🥇 Minhas Conquistas")
        
        # Formulário de Envio
        with st.expander("➕ Adicionar Nova Medalha", expanded=False):
            with st.form("nova_conquista_aluno"):
                st.write("Lutou um campeonato? Registre aqui para subir no Ranking!")
                c1, c2 = st.columns([2, 1])
                nome_camp = c1.text_input("Nome do Campeonato (Ex: Open Fortaleza)")
                medalha = c2.selectbox("Resultado", ["Ouro", "Prata", "Bronze", "Participação"])
                data_comp = st.date_input("Data do Evento", date.today())
                
                pontos_map = {"Ouro": 9, "Prata": 3, "Bronze": 1, "Participação": 0.5}
                
                if st.form_submit_button("Enviar para Aprovação"):
                    if nome_camp:
                        pts = pontos_map[medalha]
                        # Insere como PENDENTE
                        db.executar_query("""
                            INSERT INTO historico_competicoes (id_aluno, id_filial, nome_campeonato, medalha, data_competicao, pontos, status) 
                            VALUES (%s, %s, %s, %s, %s, %s, 'Pendente')
                        """, (user['id'], user['id_filial'], nome_camp, medalha, data_comp, pts))
                        st.success("Enviado! Aguarde seu professor confirmar."); time.sleep(1.5); st.rerun()
                    else: st.error("Digite o nome do campeonato.")

        st.divider()
        
        # Lista de Medalhas
        medalhas = db.executar_query("SELECT nome_campeonato, medalha, data_competicao, status FROM historico_competicoes WHERE id_aluno=%s ORDER BY data_competicao DESC", (user['id'],), fetch=True)
        
        if medalhas:
            for m in medalhas:
                cor_status = "orange" if m['status'] == 'Pendente' else "green" if m['status'] == 'Aprovado' else "red"
                icone_status = "⏳" if m['status'] == 'Pendente' else "✅" if m['status'] == 'Aprovado' else "❌"
                
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.write(f"**{m['nome_campeonato']}**")
                c1.caption(f"{m['data_competicao'].strftime('%d/%m/%Y')}")
                c2.write(f"🏅 {m['medalha']}")
                c3.markdown(f":{cor_status}[{icone_status} {m['status']}]")
                st.markdown("---")
        else:
            st.info("Nenhuma competição registrada.")