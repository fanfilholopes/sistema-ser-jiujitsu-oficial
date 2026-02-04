import streamlit as st
import database as db
import utils
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
import time

def painel_adm_filial(renderizar_sidebar=True):
    user = st.session_state.usuario
    id_filial = user['id_filial']
    perfil = user['perfil']
    
    eh_admin = perfil in ['adm_filial', 'lider']
    
    if renderizar_sidebar:
        nome_filial = db.executar_query("SELECT nome FROM filiais WHERE id=%s", (id_filial,), fetch=True)
        nome_f = nome_filial[0]['nome'] if nome_filial else "Filial"
        
        try: st.sidebar.image("logoser.jpg", width=150)
        except: pass
        st.sidebar.markdown(f"## {nome_f}")
        st.sidebar.caption(f"{utils.CARGOS.get(perfil, perfil).upper()}")
        st.sidebar.markdown("---")
        if st.sidebar.button("Sair"):
            st.session_state.logado = False
            st.rerun()

    tab_dash, tab_chamada, tab_rank, tab_grad, tab_turmas, tab_alunos = st.tabs(["📊 Painel", "✅ Chamada", "🏆 Rankings", "🎓 Graduações", "📅 Turmas", "👥 Alunos"])

    # =======================================================
    # 1. DASHBOARD
    # =======================================================
    with tab_dash:
        avisos = db.executar_query("SELECT titulo, mensagem, data_postagem FROM avisos WHERE ativo=TRUE AND publico_alvo IN ('Todos', 'Admins Filiais', 'Professores') ORDER BY id DESC", fetch=True)
        if avisos:
            with st.expander("📢 Mural de Avisos", expanded=True):
                for av in avisos:
                    st.info(f"**{av['titulo']}** ({av['data_postagem'].strftime('%d/%m')})\n\n{av['mensagem']}")
        st.write("")

        dados_status = db.executar_query("SELECT status_conta, COUNT(*) FROM usuarios WHERE id_filial=%s AND perfil IN ('aluno', 'monitor') GROUP BY status_conta", (id_filial,), fetch=True)
        mapa = {s: q for s, q in dados_status} if dados_status else {}
        qtd_ativos, qtd_inativos, qtd_pendentes = mapa.get('Ativo', 0), mapa.get('Inativo', 0), mapa.get('Pendente', 0)
        treinos_hoje = db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_filial=%s AND data_aula=CURRENT_DATE AND validado=TRUE", (id_filial,), fetch=True)[0][0]
        
        q_niver = "SELECT nome_completo, telefone FROM usuarios WHERE id_filial=%s AND status_conta='Ativo' AND perfil IN ('aluno', 'monitor') AND EXTRACT(MONTH FROM data_nascimento) = EXTRACT(MONTH FROM CURRENT_DATE) AND EXTRACT(DAY FROM data_nascimento) = EXTRACT(DAY FROM CURRENT_DATE)"
        aniversariantes = db.executar_query(q_niver, (id_filial,), fetch=True)
        qtd_niver = len(aniversariantes) if aniversariantes else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("✅ Ativos", qtd_ativos)
        c2.metric("🚫 Inativos", qtd_inativos)
        c3.metric("⏳ Pendentes", qtd_pendentes, delta="Aprovar" if qtd_pendentes > 0 else None, delta_color="inverse")
        c4.metric("🥋 Treinos Hoje", treinos_hoje)
        st.divider()

        if qtd_pendentes > 0:
            st.warning(f"🔔 **Novos Cadastros:** {qtd_pendentes} aprovações pendentes.")
            novos = db.executar_query("SELECT id, nome_completo, faixa, telefone FROM usuarios WHERE id_filial=%s AND status_conta='Pendente'", (id_filial,), fetch=True)
            cols_new = st.columns(3)
            for i, novo in enumerate(novos):
                with cols_new[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"**{novo['nome_completo']}**")
                        st.caption(f"{novo['faixa']}")
                        b_aprov, b_recus = st.columns(2)
                        if b_aprov.button("✅", key=f"acp_{novo['id']}", type="primary", use_container_width=True):
                            db.executar_query("UPDATE usuarios SET status_conta='Ativo' WHERE id=%s", (novo['id'],))
                            st.toast("Ativado!"); time.sleep(0.5); st.rerun()
                        if b_recus.button("❌", key=f"rcs_{novo['id']}", use_container_width=True):
                            db.executar_query("DELETE FROM usuarios WHERE id=%s", (novo['id'],))
                            st.toast("Recusado."); time.sleep(0.5); st.rerun()
            st.divider()

        sql_evasao = """
            SELECT u.id, u.nome_completo, u.telefone, u.faixa, MAX(c.data_aula) as ultimo_treino
            FROM usuarios u
            JOIN checkins c ON u.id = c.id_aluno
            WHERE u.id_filial=%s AND u.status_conta='Ativo' AND u.perfil IN ('aluno', 'monitor')
            GROUP BY u.id
            HAVING MAX(c.data_aula) < CURRENT_DATE - INTERVAL '14 days'
            ORDER BY ultimo_treino ASC
        """
        sumidos = db.executar_query(sql_evasao, (id_filial,), fetch=True)
        if sumidos:
            st.error(f"⚠️ Atenção! **{len(sumidos)} alunos** veteranos sumiram há mais de 2 semanas.")
            with st.expander("Ver lista de risco", expanded=True):
                for s in sumidos:
                    dias = (date.today() - s['ultimo_treino']).days
                    c_n, c_t, c_a = st.columns([2, 1, 1.5])
                    c_n.markdown(f"**{s['nome_completo']}**")
                    c_t.caption(f"Ausente há {dias} dias")
                    with c_a:
                        tel = ''.join(filter(str.isdigit, s['telefone'] or ""))
                        if tel: st.link_button("💬 Zap", f"https://wa.me/55{tel}?text=Volta pros treinos!")
                        if st.button("Inativar", key=f"ina_{s['id']}"):
                            db.executar_query("UPDATE usuarios SET status_conta='Inativo' WHERE id=%s", (s['id'],)); st.rerun()
            st.divider()

        if qtd_niver > 0:
            st.success(f"🎈 **{qtd_niver} Aniversariante(s) hoje!**")
            st.dataframe(pd.DataFrame(aniversariantes, columns=['Nome', 'WhatsApp']), use_container_width=True, hide_index=True)
            st.divider()

        d_faixa = db.executar_query("SELECT faixa, COUNT(*) as qtd FROM usuarios WHERE id_filial=%s AND perfil IN ('aluno', 'monitor') AND status_conta='Ativo' GROUP BY faixa", (id_filial,), fetch=True)
        if d_faixa:
            col_pizza, col_barras = st.columns([1, 1.5])
            cores_map = {'Branca': '#f0f0f0', 'Cinza': '#a0a0a0', 'Amarela': '#ffe135', 'Laranja': '#ff8c00', 'Verde': '#228b22', 'Azul': '#0000ff', 'Roxa': '#800080', 'Marrom': '#8b4513', 'Preta': '#000000'}
            df_graf = pd.DataFrame(d_faixa, columns=['Faixa', 'Qtd'])
            with col_pizza:
                st.markdown("##### Distribuição")
                fig_pie = px.pie(df_graf, values='Qtd', names='Faixa', hole=0.4, color='Faixa', color_discrete_map=cores_map)
                fig_pie.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_pie, use_container_width=True)
            with col_barras:
                st.markdown("##### Por Faixa")
                fig_bar = px.bar(df_graf.sort_values('Qtd', ascending=False), x='Faixa', y='Qtd', text='Qtd', color='Faixa', color_discrete_map=cores_map)
                fig_bar.update_traces(textposition='outside'); fig_bar.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_bar, use_container_width=True)

    # =======================================================
    # 2. CHAMADA
    # =======================================================
    with tab_chamada:
        pendencias = db.executar_query("SELECT c.id, u.nome_completo, t.nome as turma, t.horario FROM checkins c JOIN usuarios u ON c.id_aluno = u.id JOIN turmas t ON c.id_turma = t.id WHERE c.id_filial=%s AND c.data_aula = CURRENT_DATE AND c.validado = FALSE ORDER BY t.horario", (id_filial,), fetch=True)
        if pendencias:
            st.error(f"🔔 Existem {len(pendencias)} check-ins aguardando aprovação!")
            cols = st.columns(3)
            for i, p in enumerate(pendencias):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"**{p['nome_completo']}**")
                        st.caption(f"📍 {p['turma']} | ⏰ {p['horario']}")
                        b_ok, b_no = st.columns(2)
                        if b_ok.button("✅", key=f"adm_ok_{p['id']}", type="primary", use_container_width=True):
                            db.executar_query("UPDATE checkins SET validado=TRUE WHERE id=%s", (p['id'],)); st.toast("Confirmado!"); time.sleep(0.5); st.rerun()
                        if b_no.button("❌", key=f"adm_no_{p['id']}", use_container_width=True):
                            db.executar_query("DELETE FROM checkins WHERE id=%s", (p['id'],)); st.toast("Recusado."); time.sleep(0.5); st.rerun()
            st.divider()

        col_lista, col_filtros = st.columns([3, 1.2])
        with col_filtros:
            with st.container(border=True):
                st.markdown("#### ⚙️ Configuração")
                data_aula = st.date_input("📅 Data da Aula", value=date.today())
                turmas = db.executar_query("SELECT id, nome, horario FROM turmas WHERE id_filial=%s", (id_filial,), fetch=True)
                d_t = {f"{t['nome']} ({t['horario']})": t['id'] for t in turmas} if turmas else {}
                sel_turma = st.selectbox("Selecione a Turma", list(d_t.keys()), key="sel_turma_chamada") if d_t else None
                metric_ph = st.empty()

        with col_lista:
            if sel_turma:
                id_t = d_t[sel_turma]
                alunos = db.executar_query("SELECT id, nome_completo, faixa FROM usuarios WHERE id_turma=%s AND status_conta='Ativo' AND perfil IN ('aluno', 'monitor') ORDER BY nome_completo", (id_t,), fetch=True)
                checkins_feitos = [x[0] for x in db.executar_query("SELECT id_aluno FROM checkins WHERE id_turma=%s AND data_aula=%s AND validado=TRUE", (id_t, data_aula), fetch=True)]
                
                st.markdown(f"### 📋 Lista de Presença - {data_aula.strftime('%d/%m/%Y')}")
                with st.form("form_chamada"):
                    checks = []
                    c_alunos = st.columns(2)
                    for i, a in enumerate(alunos):
                        with c_alunos[i % 2]:
                            ja_marcado = a['id'] in checkins_feitos
                            if st.checkbox(f"{a['nome_completo']} ({a['faixa']})", value=ja_marcado, key=f"ch_{a['id']}"):
                                checks.append(a['id'])
                    st.write("")
                    if st.form_submit_button("💾 Salvar Chamada Manual", type="primary", use_container_width=True):
                        db.executar_query("DELETE FROM checkins WHERE id_turma=%s AND data_aula=%s", (id_t, data_aula))
                        for uid in checks:
                            db.executar_query("INSERT INTO checkins (id_aluno, id_turma, id_filial, data_aula, validado) VALUES (%s, %s, %s, %s, TRUE)", (uid, id_t, id_filial, data_aula))
                        st.toast(f"Chamada atualizada!"); time.sleep(0.5); st.rerun()
                
                qtd_total, qtd_pres = len(alunos), len(checkins_feitos)
                perc = int((qtd_pres/qtd_total)*100) if qtd_total > 0 else 0
                metric_ph.metric("Presença", f"{qtd_pres}/{qtd_total}", f"{perc}%")
            else: st.info("Selecione uma turma.")
        
        st.divider()
        if sel_turma and checkins_feitos:
            st.markdown("#### ✅ Alunos Confirmados nesta Data:")
            nomes = db.executar_query("SELECT nome_completo, faixa FROM usuarios WHERE id IN %s", (tuple(checkins_feitos),), fetch=True) if checkins_feitos else []
            html = ""
            cores = {'Branca': '#eee', 'Azul': '#cce5ff', 'Roxa': '#e2cfff', 'Marrom': '#e8dccc', 'Preta': '#333'}
            txts = {'Preta': 'white', 'Branca': 'black'}
            for p in nomes:
                bg = cores.get(p['faixa'], '#eee'); txt = txts.get(p['faixa'], 'black')
                html += f'<span style="background-color:{bg}; color:{txt}; padding:4px 10px; border-radius:15px; margin-right:5px; display:inline-block; margin-bottom:5px;">{p["nome_completo"]}</span>'
            st.markdown(html, unsafe_allow_html=True)

    # =======================================================
    # 3. RANKINGS (COM APROVAÇÃO DE MEDALHAS)
    # =======================================================
    with tab_rank:
        col_casca, col_comp = st.columns([1, 1])
        
        # --- CASCA GROSSA ---
        with col_casca:
            st.markdown("### 🦍 Ranking Casca Grossa")
            st.caption("Frequência de treinos validados.")
            
            sql_mes = """
                SELECT u.nome_completo, COUNT(c.id) as treinos 
                FROM checkins c JOIN usuarios u ON c.id_aluno = u.id 
                WHERE c.id_filial=%s AND c.validado=TRUE 
                AND EXTRACT(MONTH FROM c.data_aula) = %s AND EXTRACT(YEAR FROM c.data_aula) = %s
                GROUP BY u.nome_completo ORDER BY treinos DESC LIMIT 3
            """
            top3 = db.executar_query(sql_mes, (id_filial, date.today().month, date.today().year), fetch=True)
            st.markdown("##### 📅 Top 3 do Mês")
            if top3:
                for i, a in enumerate(top3): st.write(f"**{['🥇','🥈','🥉'][i]} {a['nome_completo']}** - {a['treinos']} treinos")
            else: st.info("Sem treinos este mês.")

            st.divider()
            
            sql_ano = """
                SELECT u.nome_completo, COUNT(c.id) as treinos 
                FROM checkins c JOIN usuarios u ON c.id_aluno = u.id 
                WHERE c.id_filial=%s AND c.validado=TRUE AND EXTRACT(YEAR FROM c.data_aula) = %s
                GROUP BY u.nome_completo ORDER BY treinos DESC
            """
            rank_ano = db.executar_query(sql_ano, (id_filial, date.today().year), fetch=True)
            st.markdown("##### 📆 Ranking Anual")
            if rank_ano:
                with st.expander("Ver Ranking Completo"):
                    st.dataframe(pd.DataFrame(rank_ano, columns=['Aluno', 'Treinos']), use_container_width=True)
            else: st.info("Sem dados anuais.")

        # --- COMPETIÇÕES ---
        with col_comp:
            st.markdown("### 🏅 Quadro de Medalhas")
            
            # 1. ALERTA DE PENDÊNCIAS (NOVO!)
            med_pend = db.executar_query("""
                SELECT h.id, u.nome_completo, h.nome_campeonato, h.medalha 
                FROM historico_competicoes h JOIN usuarios u ON h.id_aluno = u.id 
                WHERE h.id_filial=%s AND h.status='Pendente'
            """, (id_filial,), fetch=True)
            
            if med_pend:
                st.warning(f"🔔 **{len(med_pend)} Medalhas para Aprovar**")
                for mp in med_pend:
                    with st.container(border=True):
                        st.write(f"**{mp['nome_completo']}** - {mp['medalha']}")
                        st.caption(f"🏆 {mp['nome_campeonato']}")
                        b1, b2 = st.columns(2)
                        if b1.button("✅ Aceitar", key=f"ok_med_{mp['id']}", use_container_width=True):
                            db.executar_query("UPDATE historico_competicoes SET status='Aprovado' WHERE id=%s", (mp['id'],))
                            st.toast("Medalha confirmada!"); time.sleep(0.5); st.rerun()
                        if b2.button("❌ Recusar", key=f"no_med_{mp['id']}", use_container_width=True):
                            db.executar_query("UPDATE historico_competicoes SET status='Recusado' WHERE id=%s", (mp['id'],))
                            st.toast("Recusada."); time.sleep(0.5); st.rerun()
                st.divider()

            # 2. Formulário Admin
            with st.form("form_medalha_adm"):
                st.markdown("###### Lançar Conquista (Admin)")
                alunos_all = db.executar_query("SELECT id, nome_completo FROM usuarios WHERE id_filial=%s AND status_conta='Ativo' ORDER BY nome_completo", (id_filial,), fetch=True)
                opts_al = {u['nome_completo']: u['id'] for u in alunos_all} if alunos_all else {}
                c_sel, c_med = st.columns([2, 1])
                aluno_sel = c_sel.selectbox("Atleta", list(opts_al.keys())) if opts_al else None
                medalha = c_med.selectbox("Medalha", ["Ouro", "Prata", "Bronze", "Participação"])
                camp = st.text_input("Nome do Campeonato")
                if st.form_submit_button("🏅 Registrar (Já Aprovado)", type="primary", use_container_width=True):
                    if aluno_sel and camp:
                        pts = {"Ouro": 9, "Prata": 3, "Bronze": 1, "Participação": 0.5}[medalha]
                        db.executar_query("INSERT INTO historico_competicoes (id_aluno, id_filial, nome_campeonato, medalha, pontos, status) VALUES (%s, %s, %s, %s, %s, 'Aprovado')", (opts_al[aluno_sel], id_filial, camp, medalha, pts))
                        st.success("Registrado!"); time.sleep(1); st.rerun()
            
            st.divider()
            
            # Ranking (SÓ CONTA APROVADOS)
            rank_comp = db.executar_query("""
                SELECT u.nome_completo, SUM(hc.pontos) as total 
                FROM historico_competicoes hc JOIN usuarios u ON hc.id_aluno = u.id 
                WHERE hc.id_filial=%s AND hc.status='Aprovado' AND EXTRACT(YEAR FROM hc.data_competicao) = %s
                GROUP BY u.nome_completo ORDER BY total DESC
            """, (id_filial, date.today().year), fetch=True)
            
            if rank_comp:
                st.markdown("##### 🏆 Melhores Competidores")
                st.dataframe(pd.DataFrame(rank_comp, columns=['Atleta', 'Pontos']), use_container_width=True)
            else: st.info("Sem medalhas aprovadas este ano.")

    # =======================================================
    # 4. GRADUAÇÃO (OTIMIZADO)
    # =======================================================
    with tab_grad:
        if eh_admin:
            pend = db.executar_query("SELECT s.id, u.nome_completo, s.nova_faixa FROM solicitacoes_graduacao s JOIN usuarios u ON s.id_aluno=u.id WHERE s.id_filial=%s AND s.status='Pendente'", (id_filial,), fetch=True)
            if pend:
                st.warning("🟠 **Aguardando Autorização (Financeiro/Adm):**")
                for p in pend:
                    c1, c2 = st.columns([3,1])
                    c1.write(f"**{p['nome_completo']}** ➝ {p['nova_faixa']}")
                    if c2.button("Autorizar Exame", key=f"au_{p['id']}"):
                        db.executar_query("UPDATE solicitacoes_graduacao SET status='Aguardando Exame' WHERE id=%s", (p['id'],)); st.rerun()
                st.divider()
        
        exams = db.executar_query("SELECT s.id, u.nome_completo, s.nova_faixa FROM solicitacoes_graduacao s JOIN usuarios u ON s.id_aluno=u.id WHERE s.id_filial=%s AND s.status='Aguardando Exame'", (id_filial,), fetch=True)
        if exams:
            st.info("🥋 **Aguardando Exame Prático:**")
            for e in exams:
                c1, c2 = st.columns([3,1])
                c1.write(f"**{e['nome_completo']}** ➝ {e['nova_faixa']}")
                if c2.button("Aprovado ✅", key=f"ex_{e['id']}"):
                    db.executar_query("UPDATE solicitacoes_graduacao SET status='Aguardando Homologacao' WHERE id=%s", (e['id'],)); st.rerun()
            st.divider()

        st.markdown("#### 📡 Radar de Graduação")
        em_processo = db.executar_query("SELECT id_aluno FROM solicitacoes_graduacao WHERE status NOT IN ('Concluido', 'Recusado', 'Reprovado')", fetch=True)
        ids_em_processo = [int(x['id_aluno']) for x in em_processo] if em_processo else []
        sql_radar_otimizado = """
            SELECT u.id, u.nome_completo, u.faixa, u.graus, u.data_nascimento, u.data_ultimo_grau, u.data_inicio,
            (SELECT COUNT(*) FROM checkins c WHERE c.id_aluno = u.id AND c.validado = TRUE AND c.data_aula >= COALESCE(u.data_ultimo_grau, u.data_inicio, CURRENT_DATE)) as presencas_validas
            FROM usuarios u WHERE u.id_filial=%s AND u.perfil IN ('aluno', 'monitor') AND u.status_conta='Ativo'
        """
        alunos = db.executar_query(sql_radar_otimizado, (id_filial,), fetch=True)
        if alunos:
            cont_radar = 0
            for a in alunos:
                if int(a['id']) in ids_em_processo: continue
                pres = a['presencas_validas']
                apto, msg, prog, troca = utils.calcular_status_graduacao(a, pres)
                with st.expander(f"{'🔥' if apto else '⏳'} {a['nome_completo']} - {msg}"):
                    st.progress(prog)
                    c1, c2 = st.columns(2)
                    if c1.button("+1 Grau", key=f"g_{a['id']}"):
                        db.executar_query("UPDATE usuarios SET graus = graus + 1, data_ultimo_grau = CURRENT_DATE WHERE id=%s", (a['id'],)); st.toast("Grau adicionado!"); time.sleep(0.5); st.rerun()
                    if troca:
                        idade_atual = utils.calcular_idade_ano(a['data_nascimento'])
                        nf = utils.get_proxima_faixa(a['faixa'], idade_atual)
                        if c2.button(f"Indicar {nf}", key=f"ind_{a['id']}"):
                            db.executar_query("INSERT INTO solicitacoes_graduacao (id_aluno, id_filial, faixa_atual, nova_faixa, status) VALUES (%s, %s, %s, %s, 'Pendente')", (a['id'], id_filial, a['faixa'], nf))
                            st.success("Indicado!"); time.sleep(1); st.rerun()
                cont_radar += 1
            if cont_radar == 0: st.caption("Todos em dia.")

    # =======================================================
    # 5. TURMAS
    # =======================================================
    with tab_turmas:
        sub_tab_config, sub_tab_enturmar = st.tabs(["⚙️ Criar/Editar Turmas", "👥 Gerenciar Alunos na Turma"])
        with sub_tab_config:
            if 'edit_turma_id' not in st.session_state: st.session_state.edit_turma_id = None
            val_nome, val_dias, val_horario, val_id_prof, val_id_mon = "", "", "", None, None
            lbl_btn = "➕ Criar Turma"; expandido = False
            if st.session_state.edit_turma_id:
                dados_t = db.executar_query("SELECT * FROM turmas WHERE id=%s", (st.session_state.edit_turma_id,), fetch=True)[0]
                val_nome = dados_t['nome']; val_dias = dados_t['dias']; val_horario = dados_t['horario']
                val_id_prof = dados_t['id_professor']; val_id_mon = dados_t['id_monitor']
                lbl_btn = "💾 Salvar Alterações"; expandido = True
            with st.container(border=True):
                with st.expander(f"{'✏️ Editando Turma' if st.session_state.edit_turma_id else '➕ Nova Turma'}", expanded=expandido):
                    with st.form("form_turma"):
                        c_n, c_d, c_h = st.columns(3)
                        n = c_n.text_input("Nome (Ex: Kids)", value=val_nome)
                        d = c_d.text_input("Dias (Ex: Seg/Qua)", value=val_dias)
                        h = c_h.text_input("Horário (Ex: 19h)", value=val_horario)
                        c_prof, c_mon = st.columns(2)
                        profs = db.executar_query("SELECT id, nome_completo FROM usuarios WHERE id_filial=%s AND perfil IN ('professor', 'lider', 'adm_filial')", (id_filial,), fetch=True)
                        opts_prof = {p['nome_completo']: p['id'] for p in profs} if profs else {}
                        idx_prof = list(opts_prof.values()).index(val_id_prof) if val_id_prof in opts_prof.values() else 0
                        sel_prof = c_prof.selectbox("Professor Responsável", list(opts_prof.keys()), index=idx_prof) if opts_prof else None
                        mons = db.executar_query("SELECT id, nome_completo FROM usuarios WHERE id_filial=%s AND perfil='monitor'", (id_filial,), fetch=True)
                        opts_mon = {m['nome_completo']: m['id'] for m in mons}
                        opts_mon["--- Sem Monitor ---"] = None
                        idx_mon = list(opts_mon.values()).index(val_id_mon) if val_id_mon in opts_mon.values() else list(opts_mon.keys()).index("--- Sem Monitor ---")
                        sel_mon = c_mon.selectbox("Monitor Auxiliar", list(opts_mon.keys()), index=idx_mon)
                        c_save, c_cancel = st.columns([1, 4])
                        if c_save.form_submit_button(lbl_btn, type="primary"):
                            if n and d and h and sel_prof:
                                id_p_sel = opts_prof[sel_prof]
                                id_m_sel = opts_mon[sel_mon]
                                if st.session_state.edit_turma_id:
                                    db.executar_query("UPDATE turmas SET nome=%s, dias=%s, horario=%s, id_professor=%s, id_monitor=%s WHERE id=%s", (n, d, h, id_p_sel, id_m_sel, st.session_state.edit_turma_id))
                                    st.success("Atualizado!"); st.session_state.edit_turma_id = None; time.sleep(1); st.rerun()
                                else:
                                    db.executar_query("INSERT INTO turmas (nome, dias, horario, id_professor, id_monitor, id_filial) VALUES (%s, %s, %s, %s, %s, %s)", (n, d, h, id_p_sel, id_m_sel, id_filial))
                                    st.success("Criado!"); st.rerun()
                            else: st.error("Preencha campos.")
                        if st.session_state.edit_turma_id:
                            if c_cancel.form_submit_button("Cancelar"): st.session_state.edit_turma_id = None; st.rerun()
            ts = db.executar_query("SELECT t.id, t.nome, t.dias, t.horario, u.nome_completo as nome_prof FROM turmas t LEFT JOIN usuarios u ON t.id_professor = u.id WHERE t.id_filial=%s ORDER BY t.nome", (id_filial,), fetch=True)
            if ts:
                for t in ts:
                    qtd_t = db.executar_query("SELECT COUNT(*) FROM usuarios WHERE id_turma=%s AND status_conta='Ativo'", (t['id'],), fetch=True)[0][0]
                    with st.expander(f"🥋 {t['nome']} ({qtd_t} alunos) | Prof. {t['nome_prof']}"):
                        c1, c2, c3, c4 = st.columns([2, 2, 0.5, 0.5])
                        c1.write(f"📅 {t['dias']}"); c2.write(f"⏰ {t['horario']}")
                        if c3.button("✏️", key=f"edt_t_{t['id']}"): st.session_state.edit_turma_id = t['id']; st.rerun()
                        if c4.button("🗑️", key=f"del_t_{t['id']}"): db.executar_query("DELETE FROM turmas WHERE id=%s", (t['id'],)); st.rerun()

        with sub_tab_enturmar:
            st.markdown("##### Gestão de Elenco")
            turmas_g = db.executar_query("SELECT id, nome, horario FROM turmas WHERE id_filial=%s", (id_filial,), fetch=True)
            d_turmas_sel = {f"{t['nome']} ({t['horario']})": t['id'] for t in turmas_g} if turmas_g else {}
            sel_t_gestao = st.selectbox("Selecione a Turma", list(d_turmas_sel.keys()), key="sel_turma_gestao") if d_turmas_sel else None
            if sel_t_gestao:
                id_t_alvo = d_turmas_sel[sel_t_gestao]
                col_in, col_out = st.columns(2)
                with col_in:
                    st.success("✅ Alunos Nesta Turma")
                    alunos_in = db.executar_query("SELECT id, nome_completo FROM usuarios WHERE id_turma=%s AND status_conta='Ativo' ORDER BY nome_completo", (id_t_alvo,), fetch=True)
                    if alunos_in:
                        for a in alunos_in:
                            c_nome, c_btn = st.columns([0.8, 0.2])
                            c_nome.write(f"🥋 {a['nome_completo']}")
                            if c_btn.button("❌", key=f"rem_{a['id']}"):
                                db.executar_query("UPDATE usuarios SET id_turma=NULL WHERE id=%s", (a['id'],)); st.toast("Removido!"); time.sleep(0.5); st.rerun()
                    else: st.caption("Vazia.")
                with col_out:
                    st.warning("⚠️ Alunos Disponíveis")
                    alunos_out = db.executar_query("SELECT id, nome_completo FROM usuarios WHERE (id_turma IS NULL OR id_turma != %s) AND id_filial=%s AND status_conta='Ativo' AND perfil IN ('aluno', 'monitor') ORDER BY nome_completo", (id_t_alvo, id_filial), fetch=True)
                    filtro = st.text_input("🔎 Buscar", placeholder="Nome...")
                    for a in alunos_out:
                        if filtro.lower() in a['nome_completo'].lower():
                            c_nome, c_btn = st.columns([0.8, 0.2])
                            c_nome.write(f"{a['nome_completo']}")
                            if c_btn.button("➕", key=f"add_{a['id']}"):
                                db.executar_query("UPDATE usuarios SET id_turma=%s WHERE id=%s", (id_t_alvo, a['id'])); st.toast("Adicionado!"); time.sleep(0.5); st.rerun()

    # =======================================================
    # 6. ALUNOS
    # =======================================================
    with tab_alunos:
        if 'aluno_edit_id' not in st.session_state: st.session_state.aluno_edit_id = None
        if 'aluno_promo_id' not in st.session_state: st.session_state.aluno_promo_id = None

        if st.session_state.aluno_edit_id:
            st.info("✏️ **Editando Aluno**")
            dados_al = db.executar_query("SELECT * FROM usuarios WHERE id=%s", (st.session_state.aluno_edit_id,), fetch=True)[0]
            with st.container(border=True):
                with st.form("edit_al"):
                    ne = st.text_input("Nome", value=dados_al['nome_completo'])
                    te = st.text_input("Telefone", value=dados_al['telefone'])
                    em = st.text_input("Email", value=dados_al['email'])
                    c_b1, c_b2 = st.columns(2)
                    if c_b1.form_submit_button("💾 Salvar", use_container_width=True):
                        db.executar_query("UPDATE usuarios SET nome_completo=%s, telefone=%s, email=%s WHERE id=%s", (ne, te, em, st.session_state.aluno_edit_id))
                        st.success("Atualizado!"); st.session_state.aluno_edit_id = None; time.sleep(1); st.rerun()
                    if c_b2.form_submit_button("Cancelar", use_container_width=True): st.session_state.aluno_edit_id = None; st.rerun()

        elif st.session_state.aluno_promo_id:
            st.warning("⭐ **Promover Aluno**")
            dados_promo = db.executar_query("SELECT nome_completo FROM usuarios WHERE id=%s", (st.session_state.aluno_promo_id,), fetch=True)[0]
            st.write(f"Promover **{dados_promo['nome_completo']}** para:")
            with st.container(border=True):
                novo_cargo = st.selectbox("Novo Cargo:", ["monitor", "professor"])
                c_p1, c_p2 = st.columns(2)
                if c_p1.button("✅ Confirmar", use_container_width=True):
                    db.executar_query("UPDATE usuarios SET perfil=%s WHERE id=%s", (novo_cargo, st.session_state.aluno_promo_id))
                    st.success("Promovido!"); st.session_state.aluno_promo_id = None; time.sleep(1.5); st.rerun()
                if c_p2.button("Cancelar", use_container_width=True): st.session_state.aluno_promo_id = None; st.rerun()

        else:
            tab_l, tab_n = st.tabs(["📋 Lista de Alunos", "➕ Matricular Novo"])
            with tab_l:
                c_h1, c_h2, c_h3 = st.columns([2, 1, 1.5])
                c_h1.markdown("**Nome**"); c_h2.markdown("**Faixa**"); c_h3.markdown("**Ações**")
                st.markdown('<hr style="margin: 5px 0; border: none; border-top: 1px solid #333;">', unsafe_allow_html=True)
                filtro_status = st.radio("Exibir:", ["Ativos", "Inativos"], horizontal=True)
                st_filtro = "Ativo" if filtro_status == "Ativos" else "Inativo"
                membros = db.executar_query("SELECT id, nome_completo, faixa, perfil FROM usuarios WHERE id_filial=%s AND status_conta=%s AND perfil IN ('aluno', 'monitor') ORDER BY nome_completo", (id_filial, st_filtro), fetch=True)
                if membros:
                    for m in membros:
                        c1, c2, c3 = st.columns([2, 1, 1.5])
                        icon_perfil = "🧢" if m['perfil'] == 'monitor' else ""
                        c1.write(f"{m['nome_completo']} {icon_perfil}")
                        c2.caption(f"{m['faixa']}")
                        with c3:
                            b_ed, b_up, b_del = st.columns([1, 1, 1], gap="small")
                            if b_ed.button("✏️", key=f"edt_{m['id']}"): st.session_state.aluno_edit_id = m['id']; st.rerun()
                            if st_filtro == 'Ativo':
                                if b_up.button("⭐", key=f"prm_{m['id']}"): st.session_state.aluno_promo_id = m['id']; st.rerun()
                                if b_del.button("🚫", key=f"del_{m['id']}", help="Inativar"):
                                    db.executar_query("UPDATE usuarios SET status_conta='Inativo' WHERE id=%s", (m['id'],))
                                    st.toast("Inativado!"); time.sleep(0.5); st.rerun()
                            else:
                                if b_del.button("♻️", key=f"reat_{m['id']}", help="Reativar"):
                                    db.executar_query("UPDATE usuarios SET status_conta='Ativo' WHERE id=%s", (m['id'],))
                                    st.toast("Reativado!"); time.sleep(0.5); st.rerun()
                        st.markdown('<hr style="margin: 2px 0; border: none; border-top: 1px solid #2b2b2b;">', unsafe_allow_html=True)
                else: st.info(f"Nenhum aluno {st_filtro.lower()}.")

            with tab_n:
                st.subheader("Solicitar Nova Matrícula")
                st.info("ℹ️ Novos alunos entrarão como **Pendentes** e precisarão de aprovação no Painel Principal.")
                turmas = db.executar_query("SELECT id, nome FROM turmas WHERE id_filial=%s", (id_filial,), fetch=True)
                opts_turma = {t['nome']: t['id'] for t in turmas} if turmas else {}
                c_data, c_aviso = st.columns([1, 2])
                nasc = c_data.date_input("Nascimento", value=date(2015, 1, 1), min_value=date(1920, 1, 1), max_value=date.today())
                idade = (date.today() - nasc).days // 365
                is_kid = idade < 16
                if is_kid: c_aviso.warning(f"👶 KIDS ({idade} anos) - Resp. Obrigatório.")
                else: c_aviso.success(f"🥋 ADULTO ({idade} anos)")

                with st.form("form_aluno"):
                    c1, c2 = st.columns([2, 1])
                    nome = c1.text_input("Nome Completo")
                    turma = c2.selectbox("Turma", list(opts_turma.keys())) if opts_turma else None
                    c3, c4 = st.columns(2)
                    faixa = c3.selectbox("Faixa", utils.ORDEM_FAIXAS)
                    graus = c4.selectbox("Graus", [0,1,2,3,4])
                    c5, c6 = st.columns(2)
                    dt_inicio = c5.date_input("Início", date.today())
                    dt_ult = c6.date_input("Último Grau", value=None)
                    c7, c8 = st.columns(2)
                    zap = c7.text_input("WhatsApp")
                    email = c8.text_input("E-mail (Login)")
                    nm_resp, tel_resp = None, None
                    if is_kid:
                        st.divider(); st.markdown("### 👨‍👩‍👧 Responsável")
                        c_r1, c_r2 = st.columns(2)
                        nm_resp = c_r1.text_input("Nome Resp.")
                        tel_resp = c_r2.text_input("WhatsApp Resp.")

                    if st.form_submit_button("Enviar Solicitação"):
                        if not turma: st.error("Selecione turma.")
                        elif is_kid and not nm_resp: st.error("Responsável obrigatório.")
                        else:
                            ug = dt_ult if dt_ult else dt_inicio
                            res = db.executar_query("""INSERT INTO usuarios (nome_completo, email, senha, telefone, data_nascimento, faixa, graus, id_filial, id_turma, perfil, status_conta, data_inicio, data_ultimo_grau, nome_responsavel, telefone_responsavel) VALUES (%s, %s, '123', %s, %s, %s, %s, %s, %s, 'aluno', 'Pendente', %s, %s, %s, %s)""", (nome, email, zap, nasc, faixa, graus, id_filial, opts_turma[turma], dt_inicio, ug, nm_resp, tel_resp))
                            if res == "ERRO_DUPLICADO": st.error("Email já existe!")
                            elif res: st.success("Solicitação enviada! Aprove o aluno no Painel Principal."); time.sleep(1.5); st.rerun()