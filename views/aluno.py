# views/aluno.py
import streamlit as st
import database as db
import utils
import pandas as pd
from datetime import date
import time
from core.motores_graduacao import calcular_status_graduacao

def painel_aluno(renderizar_sidebar=True):
    user = st.session_state.usuario
    
    # --- CORES DAS FAIXAS ---
    CORES_FAIXAS = {
        'Branca': '#F0F0F0', 'Cinza': '#A0A0A0', 'Amarela': '#FFD700',
        'Laranja': '#FF8C00', 'Verde': '#228B22', 'Azul': '#0000FF',
        'Roxa': '#800080', 'Marrom': '#8B4513', 'Preta': '#000000',
        'Cinza/Branca': '#A0A0A0', 'Cinza/Preta': '#A0A0A0',
        'Amarela/Branca': '#FFD700', 'Amarela/Preta': '#FFD700',
        'Laranja/Branca': '#FF8C00', 'Laranja/Preta': '#FF8C00',
        'Verde/Branca': '#228B22', 'Verde/Preta': '#228B22'
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
    # --- SIDEBAR E NAVEGAÇÃO (HISTÓRICO REMOVIDO) ---
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
        
        st.sidebar.markdown("### 📌 Menu")
        # Removido "📜 Histórico" da lista
        menu_selecionado = st.sidebar.radio(
            "Navegação", 
            ["🏠 Meu Tatame", "🏅 Competições"], 
            label_visibility="collapsed"
        )

        st.sidebar.markdown("---")
        if st.sidebar.button("Sair", key="sair_aluno"):
            st.session_state.logado = False
            st.rerun()
    else:
        # Menu horizontal para o monitor (sem Histórico)
        menu_selecionado = st.radio(
            "Navegação do Aluno", 
            ["🏠 Meu Tatame", "🏅 Competições"], 
            horizontal=True,
            label_visibility="collapsed"
        )
        st.divider()

    # =======================================================
    # CONTEÚDO PRINCIPAL: MEU TATAME
    # =======================================================
    if menu_selecionado == "🏠 Meu Tatame":
        
        # 1. TOPO: CHECK-IN E AVISOS
        c_topo_check, c_topo_aviso = st.columns([1, 2])
        
        with c_topo_check:
            st.markdown("##### 📍 Presença Hoje")
            dados_checkin = db.executar_query("SELECT validado FROM checkins WHERE id_aluno=%s AND data_aula=CURRENT_DATE", (user['id'],), fetch=True)
            if dados_checkin:
                if dados_checkin[0][0]: st.success("✅ Confirmada!")
                else: st.warning("⏳ Aguardando Prof.")
            else:
                if st.button("📲 Fazer Check-in", type="primary", use_container_width=True):
                    if user['id_turma']:
                        db.executar_query("INSERT INTO checkins (id_aluno, id_turma, id_filial, data_aula, validado) VALUES (%s, %s, %s, CURRENT_DATE, FALSE)", 
                                         (user['id'], user['id_turma'], user['id_filial']))
                        st.toast("Check-in enviado!"); time.sleep(1); st.rerun()
                    else: st.error("Você não possui turma vinculada.")

        with c_topo_aviso:
            avisos = db.executar_query("SELECT titulo, mensagem FROM avisos WHERE ativo=TRUE AND publico_alvo IN ('Todos', 'Alunos') ORDER BY id DESC LIMIT 1", fetch=True)
            if avisos:
                with st.container(border=True):
                    st.markdown(f"📢 **{avisos[0]['titulo']}**")
                    st.caption(avisos[0]['mensagem'])
            else:
                st.info("Treine com constância para subir no ranking da equipe!")

        st.divider()

        # 2. MEIO: CARTEIRINHA E RANKING (POR TURMA)
        c_card, c_ranking = st.columns([1.2, 1.8])
        
        with c_card:
            cor_faixa = CORES_FAIXAS.get(user['faixa'], '#ccc')
            cor_texto_tag = 'black' if 'Branca' in user['faixa'] or 'Amarela' in user['faixa'] else 'white'

            html_card = f"""
            <div style="background-color: #1E1E1E; padding: 20px; border-radius: 12px; border-left: 6px solid {cor_faixa}; box-shadow: 0 4px 10px rgba(0,0,0,0.4);">
                <small style="color:#888; text-transform:uppercase; letter-spacing:1px;">Aluno Oficial</small>
                <h3 style="margin:5px 0 0 0; color:white;">{user['nome_completo']}</h3>
                <div style="display:flex; gap:10px; align-items:center; margin: 10px 0;">
                    <div style="background-color: {cor_faixa}; color: {cor_texto_tag}; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size:0.9em;">
                        {user['faixa']} {user['graus']}º
                    </div>
                </div>
                <div style="background-color:#2b2b2b; padding:10px; border-radius:8px;">
                    <p style="margin:0; color:#888; font-size:0.8em;">TURMA</p>
                    <p style="margin:2px 0 0 0; color:white; font-weight:500;">{nome_turma}</p>
                    <p style="margin:0; color:#aaa; font-size:0.8em;">{detalhes_turma}</p>
                </div>
            </div>
            """
            st.markdown(html_card, unsafe_allow_html=True)

        with c_ranking:
            st.markdown(f"##### 🏆 Ranking Casca Grossa ({nome_turma})")
            r1, r2, r3 = st.columns(3)
            
            def obter_posicao(query, params, user_id):
                rank = db.executar_query(query, params, fetch=True)
                for idx, row in enumerate(rank or []):
                    if row['id_aluno'] == user_id:
                        return f"{idx + 1}º"
                return "-"

            # Ranking Mês Turma
            sql_mes = """
                SELECT id_aluno, COUNT(*) as qtd FROM checkins 
                WHERE id_filial=%s AND id_turma=%s AND validado=TRUE 
                AND EXTRACT(MONTH FROM data_aula) = EXTRACT(MONTH FROM CURRENT_DATE) 
                AND EXTRACT(YEAR FROM data_aula) = EXTRACT(YEAR FROM CURRENT_DATE)
                GROUP BY id_aluno ORDER BY qtd DESC
            """
            t_mes = db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s AND validado=TRUE AND EXTRACT(MONTH FROM data_aula) = EXTRACT(MONTH FROM CURRENT_DATE) AND EXTRACT(YEAR FROM data_aula) = EXTRACT(YEAR FROM CURRENT_DATE)", (user['id'],), fetch=True)[0][0]
            pos_mes = obter_posicao(sql_mes, (user['id_filial'], user['id_turma']), user['id'])
            with r1:
                st.metric("Treinos (Mês)", pos_mes)
                st.markdown(f"<p style='font-size: 0.8em; color: #888; margin-top: -15px;'>{t_mes} treinos</p>", unsafe_allow_html=True)
            
            # Ranking Ano Turma
            sql_ano = """
                SELECT id_aluno, COUNT(*) as qtd FROM checkins 
                WHERE id_filial=%s AND id_turma=%s AND validado=TRUE AND EXTRACT(YEAR FROM data_aula) = %s
                GROUP BY id_aluno ORDER BY qtd DESC
            """
            t_ano = db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s AND validado=TRUE AND EXTRACT(YEAR FROM data_aula) = %s", (user['id'], date.today().year), fetch=True)[0][0]
            pos_ano = obter_posicao(sql_ano, (user['id_filial'], user['id_turma'], date.today().year), user['id'])
            with r2:
                st.metric("Treinos (Ano)", pos_ano)
                st.markdown(f"<p style='font-size: 0.8em; color: #888; margin-top: -15px;'>{t_ano} treinos</p>", unsafe_allow_html=True)
            
            # Ranking Competição (Filial)
            sql_pts = "SELECT id_aluno, SUM(pontos) as total FROM historico_competicoes WHERE id_filial=%s AND status='Aprovado' GROUP BY id_aluno ORDER BY total DESC"
            pts_comp = db.executar_query("SELECT SUM(pontos) FROM historico_competicoes WHERE id_aluno=%s AND status='Aprovado'", (user['id'],), fetch=True)[0][0] or 0
            pos_pts = obter_posicao(sql_pts, (user['id_filial'],), user['id'])
            with r3:
                st.metric("Pontos Comp.", pos_pts)
                st.markdown(f"<p style='font-size: 0.8em; color: #888; margin-top: -15px;'>{pts_comp} pts</p>", unsafe_allow_html=True)

            # Jornada Técnica
            data_ref_grad = user['data_ultimo_grau'] or user['data_inicio'] or date(2020,1,1)
            presencas_p = db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s AND validado=TRUE AND data_aula >= %s", (user['id'], data_ref_grad), fetch=True)[0][0]
            apto, msg_meta, _ = calcular_status_graduacao(user, presencas_p)
            with st.container(border=True):
                st.markdown(f"🥋 **Sua Jornada:** {msg_meta}")

        st.divider()

        # 3. HISTÓRICO INTEGRADO (PRESENÇAS ESQ | GRADUAÇÃO DIR)
        c_hist_pres, c_hist_grad = st.columns([1.5, 1])

        with c_hist_pres:
            st.markdown("##### 📅 Presenças por Mês")
            hist_raw = db.executar_query("SELECT data_aula FROM checkins WHERE id_aluno=%s AND validado=TRUE ORDER BY data_aula DESC", (user['id'],), fetch=True)
            if hist_raw:
                df_h = pd.DataFrame(hist_raw); df_h.columns = ['data_aula']; df_h['data_aula'] = pd.to_datetime(df_h['data_aula'])
                df_h['mes_ref'] = df_h['data_aula'].dt.strftime('%m/%Y')
                df_h['mes_nome'] = df_h['data_aula'].dt.strftime('%B de %Y')
                for mes in df_h['mes_ref'].unique():
                    dados_mes = df_h[df_h['mes_ref'] == mes]
                    with st.expander(f"🗓️ {dados_mes['mes_nome'].iloc[0].title()} ({len(dados_mes)})", expanded=False):
                        cols = st.columns(3)
                        for i, d in enumerate(dados_mes['data_aula'].dt.strftime('%d/%m (%a)')):
                            cols[i % 3].markdown(f"✅ {d}")
            else: st.info("Sem treinos.")

        with c_hist_grad:
            st.markdown("##### 🥋 Evolução Técnica")
            grad_hist = db.executar_query("SELECT faixa, grau, data_graduacao FROM historico_graduacoes WHERE id_aluno=%s ORDER BY data_graduacao DESC", (user['id'],), fetch=True)
            if grad_hist:
                for g in grad_hist:
                    with st.container(border=True):
                        st.markdown(f"**{g['faixa']} - {g['grau']}º Grau**")
                        st.caption(f"🗓️ {g['data_graduacao'].strftime('%d/%m/%Y')}")
            else:
                with st.container(border=True):
                    st.markdown(f"**{user['faixa']} - {user['graus']}º Grau**")
                    st.caption(f"🗓️ Início: {user['data_inicio'].strftime('%d/%m/%Y')}")

    # =======================================================
    # ABA: COMPETIÇÕES
    # =======================================================
    elif menu_selecionado == "🏅 Competições":
        st.markdown("### 🥇 Minhas Conquistas")
        with st.expander("➕ Adicionar Nova Medalha"):
            with st.form("nova_conquista_aluno"):
                c1, c2 = st.columns([2, 1])
                nome_camp = c1.text_input("Campeonato")
                medalha = c2.selectbox("Resultado", ["Ouro", "Prata", "Bronze", "Participação"])
                data_comp = st.date_input("Data do Evento", date.today())
                if st.form_submit_button("Enviar para Aprovação"):
                    pts = {"Ouro": 9, "Prata": 3, "Bronze": 1, "Participação": 0.5}[medalha]
                    db.executar_query("INSERT INTO historico_competicoes (id_aluno, id_filial, nome_campeonato, medalha, data_competicao, pontos, status) VALUES (%s, %s, %s, %s, %s, %s, 'Pendente')", 
                                     (user['id'], user['id_filial'], nome_camp, medalha, data_comp, pts))
                    st.success("Enviado para análise!"); time.sleep(1); st.rerun()

        st.divider()
        medalhas = db.executar_query("SELECT nome_campeonato, medalha, data_competicao, status FROM historico_competicoes WHERE id_aluno=%s ORDER BY data_competicao DESC", (user['id'],), fetch=True)
        if medalhas:
            for m in medalhas:
                cor = "orange" if m['status'] == 'Pendente' else "green"
                st.write(f"**{m['nome_campeonato']}** - 🏅 {m['medalha']} (:{cor}[{m['status']}])")