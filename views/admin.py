import streamlit as st
import database as db
import utils
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
import time
import os

def painel_adm_filial(renderizar_sidebar=True):
    user = st.session_state.usuario
    id_filial = user['id_filial']
    perfil = user['perfil']
    
    eh_admin = perfil in ['adm_filial', 'lider']
    
    # --- AUTO-CORREÇÃO DE BANCO DE DADOS (PATCH DE LIMPEZA GERAL) ---
    
    # 1. Resolve o bug do 1º Grau antecipado (Sincroniza o relógio)
    db.executar_query("""
        UPDATE usuarios u
        SET data_ultimo_grau = (
            SELECT MAX(data_graduacao) 
            FROM historico_graduacoes 
            WHERE id_aluno = u.id
        )
        WHERE u.graus = 0 
        AND (
            u.data_ultimo_grau < (SELECT MAX(data_graduacao) FROM historico_graduacoes WHERE id_aluno = u.id)
            OR u.data_ultimo_grau IS NULL
        )
    """)

    # 2. Limpa solicitações duplicadas
    db.executar_query("""
        DELETE FROM solicitacoes_graduacao
        WHERE id NOT IN (
            SELECT MAX(id) FROM solicitacoes_graduacao 
            WHERE status IN ('Pendente', 'Aceito', 'Realizado') 
            GROUP BY id_aluno
        ) AND status IN ('Pendente', 'Aceito', 'Realizado')
    """)

    # 3. Restaura a faixa de quem ficou com "A Definir"
    db.executar_query("""
        UPDATE usuarios u
        SET faixa = COALESCE(
            (SELECT faixa FROM historico_graduacoes WHERE id_aluno = u.id AND faixa != 'A Definir' ORDER BY data_graduacao DESC LIMIT 1),
            'Branca'
        )
        WHERE faixa = 'A Definir'
    """)

    # =======================================================
    # --- NAVEGAÇÃO & SIDEBAR ---
    # =======================================================
    if renderizar_sidebar:
        nome_filial = db.executar_query("SELECT nome FROM filiais WHERE id=%s", (id_filial,), fetch=True)
        nome_f = nome_filial[0]['nome'] if nome_filial else "Filial"
        
        try: 
            st.sidebar.image("logoser.jpg", width=150)
        except: 
            pass
        
        st.sidebar.markdown(f"## {nome_f}")
        st.sidebar.caption(f"Olá, {user['nome_completo'].strip()}")
        st.sidebar.caption(f"🛡️ {utils.CARGOS.get(perfil, perfil).upper()}")
        st.sidebar.markdown("---")
        
        menu_selecionado = st.sidebar.radio(
            "Navegação", 
            ["📊 Painel", "✅ Chamada", "🏆 Rankings", "🎓 Graduações", "📅 Turmas", "👥 Alunos"], 
            label_visibility="collapsed"
        )
        st.sidebar.markdown("---")
        
        if st.sidebar.button("Sair", use_container_width=True):
            st.session_state.logado = False
            st.rerun()
    else:
        menu_selecionado = st.radio(
            "Navegação da Filial", 
            ["📊 Painel", "✅ Chamada", "🏆 Rankings", "🎓 Graduações", "📅 Turmas", "👥 Alunos"], 
            horizontal=True,
            label_visibility="collapsed"
        )
        st.divider()

    # =======================================================
    # 1. DASHBOARD (PAINEL DE CONTROLE)
    # =======================================================
    if menu_selecionado == "📊 Painel":
        # --- MURAL DE AVISOS ---
        avisos = db.executar_query("""
            SELECT titulo, mensagem, data_postagem FROM avisos 
            WHERE ativo=TRUE AND publico_alvo IN ('Todos', 'Admins Filiais', 'Professores') 
            ORDER BY id DESC LIMIT 3
        """, fetch=True)
        if avisos:
            with st.expander("📢 Mural de Avisos", expanded=True):
                for av in avisos:
                    st.info(f"{av['titulo']} ({av['data_postagem'].strftime('%d/%m')})\n\n{av['mensagem']}")
        
        # --- MÉTRICAS RÁPIDAS ---
        dados_status = db.executar_query("SELECT status_conta, COUNT(*) FROM usuarios WHERE id_filial=%s AND perfil IN ('aluno', 'monitor') GROUP BY status_conta", (id_filial,), fetch=True)
        mapa = {s: q for s, q in dados_status} if dados_status else {}
        qtd_pendentes = mapa.get('Pendente', 0)
        
        treinos_hoje = db.executar_query("SELECT COUNT(*) FROM checkins WHERE data_aula=CURRENT_DATE AND id_filial=%s AND validado=TRUE", (id_filial,), fetch=True)[0][0]
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("✅ Ativos", mapa.get('Ativo', 0))
        c2.metric("🚫 Inativos", mapa.get('Inativo', 0))
        c3.metric("⏳ Pendentes", qtd_pendentes, delta="Aprovar" if qtd_pendentes > 0 else None, delta_color="inverse")
        c4.metric("🥋 No Tatame Hoje", treinos_hoje)
        st.divider()

        # --- SEÇÃO DE APROVAÇÃO DE NOVOS ALUNOS ---
        if qtd_pendentes > 0:
            st.warning(f"🔔 Existem {qtd_pendentes} novos cadastros aguardando aprovação!")
            novos = db.executar_query("""
                SELECT id, nome_completo, faixa, graus, telefone, data_nascimento 
                FROM usuarios WHERE id_filial=%s AND status_conta='Pendente'
            """, (id_filial,), fetch=True)
            
            cols_new = st.columns(3)
            for i, novo in enumerate(novos):
                with cols_new[i % 3]:
                    with st.container(border=True):
                        idade_n = utils.calcular_idade_ano(novo['data_nascimento'])
                        st.markdown(f"{novo['nome_completo'].strip()}")
                        st.caption(f"{novo['faixa']} ({novo['graus']}º G) | 🎂 {idade_n} anos")
                        
                        b_aprov, b_recus = st.columns(2)
                        if b_aprov.button("✅ Aprovar", key=f"acp_p_{novo['id']}", use_container_width=True, type="primary"):
                            db.executar_query("UPDATE usuarios SET status_conta='Ativo' WHERE id=%s", (novo['id'],))
                            db.registrar_nova_faixa(novo['id'], novo['faixa'], manter_graus=True)
                            st.rerun()
                            
                        if b_recus.button("❌ Recusar", key=f"rcs_p_{novo['id']}", use_container_width=True):
                            db.executar_query("DELETE FROM usuarios WHERE id=%s", (novo['id'],))
                            st.rerun()
            st.divider()

        # --- BLOCO INTERMEDIÁRIO: EVASÃO E ANIVERSARIANTES ---
        col_esq, col_dir = st.columns([1.2, 1])

        with col_esq:
            st.subheader("⚠️ Alerta de Evasão (+21 dias)")
            sql_evasao = """
                SELECT u.id, u.nome_completo, u.telefone, u.faixa, MAX(c.data_aula) as ultimo_treino
                FROM usuarios u 
                LEFT JOIN checkins c ON u.id = c.id_aluno
                WHERE u.id_filial=%s AND u.status_conta='Ativo' AND u.perfil='aluno'
                GROUP BY u.id, u.nome_completo, u.telefone, u.faixa
                HAVING MAX(c.data_aula) < CURRENT_DATE - INTERVAL '21 days' 
                   OR MAX(c.data_aula) IS NULL
                ORDER BY ultimo_treino ASC NULLS FIRST
            """
            sumidos = db.executar_query(sql_evasao, (id_filial,), fetch=True)
            
            if sumidos:
                for s in sumidos:
                    with st.container(border=True):
                        c_n, c_z, c_i = st.columns([2, 1, 1])
                        ult_t = s['ultimo_treino'].strftime('%d/%m/%Y') if s['ultimo_treino'] else "Nunca treinou"
                        dias_s = (date.today() - s['ultimo_treino']).days if s['ultimo_treino'] else "∞"
                        c_n.markdown(f"{s['nome_completo'].strip()}") 
                        c_n.caption(f"Último: {ult_t} ({dias_s} dias)")
                        
                        tel_s = ''.join(filter(str.isdigit, str(s['telefone'] or "")))
                        msg_s = f"Olá {s['nome_completo'].strip()}, sentimos sua falta na SER Jiu-Jitsu!"
                        c_z.link_button("💬", f"https://wa.me/55{tel_s}?text={msg_s}", use_container_width=True, help="Enviar mensagem")
                        if c_i.button("🚫", key=f"ina_p_{s['id']}", use_container_width=True, help="Inativar aluno"):
                            db.executar_query("UPDATE usuarios SET status_conta='Inativo' WHERE id=%s", (s['id'],))
                            st.rerun()
            else:
                st.success("Nenhum aluno em risco de evasão.")

        with col_dir:
            st.subheader("🎂 Aniversariantes do Mês")
            sql_n = """
                SELECT nome_completo, data_nascimento, telefone, EXTRACT(DAY FROM data_nascimento) as dia
                FROM usuarios WHERE id_filial=%s AND status_conta='Ativo'
                AND EXTRACT(MONTH FROM data_nascimento) = EXTRACT(MONTH FROM CURRENT_DATE) ORDER BY dia
            """
            aniversariantes = db.executar_query(sql_n, (id_filial,), fetch=True)
            if aniversariantes:
                hoje_d = date.today().day
                for n in aniversariantes:
                    eh_h = int(n['dia']) == hoje_d
                    with st.container(border=True):
                        st.markdown(f"{'🎉 HOJE | ' if eh_h else ''}{int(n['dia']):02d} - {n['nome_completo'].strip()}")
                        if eh_h:
                            t_n = ''.join(filter(str.isdigit, str(n['telefone'] or "")))
                            st.link_button("🥳 Dar Parabéns", f"https://wa.me/55{t_n}?text=Parabéns!", type="primary", use_container_width=True)
            else:
                st.caption("Sem aniversários este mês.")

        st.divider()

        # --- BLOCO INFERIOR: GRÁFICO DE DISTRIBUIÇÃO ---
        st.subheader("📊 Distribuição de Alunos por Faixa")
        dados_f = db.executar_query("""
            SELECT faixa, COUNT(*) as qtd FROM usuarios 
            WHERE id_filial=%s AND status_conta='Ativo' AND perfil='aluno' GROUP BY faixa
        """, (id_filial,), fetch=True)
        
        if dados_f:
            df_f = pd.DataFrame(dados_f, columns=['Faixa', 'Qtd'])
            c_map = {
                'Branca': '#FFFFFF', 'Cinza/Branca': '#E0E0E0', 'Cinza': '#808080', 'Cinza/Preta': '#4F4F4F',
                'Amarela/Branca': '#FFFACD', 'Amarela': '#FFFF00', 'Amarela/Preta': '#BDB76B',
                'Laranja/Branca': '#FFDAB9', 'Laranja': '#FFA500', 'Laranja/Preta': '#FF8C00',
                'Verde/Branca': '#90EE90', 'Verde': '#008000', 'Verde/Preta': '#006400',
                'Azul': '#0000FF', 'Roxa': '#8A2BE2', 'Marrom': '#8B4513', 'Preta': '#000000'
            }
            fig = px.pie(df_f, values='Qtd', names='Faixa', hole=0.4, color='Faixa', color_discrete_map=c_map)
            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=350)
            
            c_g1, c_g2, c_g3 = st.columns([1, 2, 1])
            with c_g2:
                st.plotly_chart(fig, use_container_width=True)

    # =======================================================
    # 2. CHAMADA
    # =======================================================
    elif menu_selecionado == "✅ Chamada":
        st.title("✅ Controle de Presença")

        sql_checkins = """
            SELECT c.id, u.id as id_aluno, u.nome_completo, u.faixa, t.nome as nome_turma
            FROM checkins c 
            JOIN usuarios u ON c.id_aluno = u.id 
            JOIN turmas t ON c.id_turma = t.id 
            WHERE c.id_filial=%s AND c.data_aula=CURRENT_DATE AND c.validado = FALSE 
        """
        pendencias = db.executar_query(sql_checkins, (id_filial,), fetch=True)
        
        if pendencias:
            with st.container(border=True):
                st.subheader(f"🔔 Check-ins Aguardando Validação ({len(pendencias)})")
                
                if st.button("⚡ Aprovar Todos", type="primary"):
                    for p in pendencias:
                        db.executar_query("UPDATE checkins SET validado=TRUE WHERE id=%s", (p['id'],))
                        db.executar_query("INSERT INTO presencas (id_aluno, data_presenca, metodo) VALUES (%s, CURRENT_DATE, 'Check-in')", (p['id_aluno'],))
                    st.success("Todos aprovados!"); time.sleep(0.5); st.rerun()

                cols_p = st.columns(4)
                for idx, p in enumerate(pendencias):
                    with cols_p[idx % 4]:
                        with st.container(border=True):
                            st.write(p['nome_completo'].strip())
                            st.caption(f"{p['faixa']} | {p['nome_turma']}")
                            
                            b_c1, b_c2 = st.columns(2)
                            if b_c1.button("✅", key=f"v_ok_{p['id']}", help="Confirmar"):
                                db.executar_query("UPDATE checkins SET validado=TRUE WHERE id=%s", (p['id'],))
                                db.executar_query("INSERT INTO presencas (id_aluno, data_presenca, metodo) VALUES (%s, CURRENT_DATE, 'Check-in')", (p['id_aluno'],))
                                st.rerun()
                            if b_c2.button("❌", key=f"v_no_{p['id']}", help="Recusar"):
                                db.executar_query("DELETE FROM checkins WHERE id=%s", (p['id'],))
                                st.rerun()
            st.divider()

        col_filtros, col_manual = st.columns([1, 2.5])
        
        with col_filtros:
            with st.container(border=True):
                st.markdown("#### ⚙️ Filtros")
                data_aula = st.date_input("📅 Data", value=date.today(), format="DD/MM/YYYY")
                data_br = data_aula.strftime('%d/%m/%Y')
                
                turmas_raw = db.executar_query("SELECT id, nome, horario FROM turmas WHERE id_filial=%s ORDER BY horario", (id_filial,), fetch=True)
                d_t = {f"{t['nome']} ({t['horario']})": t['id'] for t in turmas_raw} if turmas_raw else {}
                
                sel_turma_txt = st.selectbox("Selecione a Turma", ["Escolha uma Turma"] + list(d_t.keys()))
                id_t_filtro = d_t.get(sel_turma_txt)

        with col_manual:
            if id_t_filtro:
                st.subheader(f"📋 Chamada Manual ({data_br})")
                
                alunos_turma = db.executar_query("SELECT id, nome_completo FROM usuarios WHERE id_turma=%s AND status_conta='Ativo' ORDER BY nome_completo", (id_t_filtro,), fetch=True)
                ids_presentes = [x[0] for x in db.executar_query("""
                    SELECT id_aluno FROM presencas 
                    WHERE data_presenca=%s AND id_aluno IN (SELECT id FROM usuarios WHERE id_turma=%s)
                """, (data_aula, id_t_filtro), fetch=True)]

                with st.form("form_chamada_final"):
                    cols_al = st.columns(2)
                    novos_marcados = []
                    for idx, al in enumerate(alunos_turma):
                        is_p = al['id'] in ids_presentes
                        if cols_al[idx % 2].checkbox(al['nome_completo'].strip(), value=is_p, key=f"f_man_{al['id']}"):
                            novos_marcados.append(al['id'])
                    
                    if st.form_submit_button("💾 Salvar Chamada Oficial", type="primary", use_container_width=True):
                        db.executar_query("DELETE FROM presencas WHERE data_presenca=%s AND id_aluno IN (SELECT id FROM usuarios WHERE id_turma=%s)", (data_aula, id_t_filtro))
                        db.executar_query("DELETE FROM checkins WHERE data_aula=%s AND id_turma=%s", (data_aula, id_t_filtro))
                        
                        for uid in novos_marcados:
                            db.executar_query("INSERT INTO presencas (id_aluno, data_presenca, metodo) VALUES (%s, %s, 'Manual')", (uid, data_aula))
                            db.executar_query("INSERT INTO checkins (id_aluno, id_turma, id_filial, data_aula, validado) VALUES (%s, %s, %s, %s, TRUE)", (uid, id_t_filtro, id_filial, data_aula))
                        st.success("Chamada salva!"); time.sleep(0.5); st.rerun()
            else:
                st.info("👈 Selecione uma turma para realizar a chamada manual.")

        if id_t_filtro:
            st.write("")
            st.divider()
            
            presentes_detalhes = db.executar_query("""
                SELECT u.nome_completo, u.faixa 
                FROM usuarios u 
                JOIN presencas p ON u.id = p.id_aluno 
                WHERE p.data_presenca = %s AND u.id_turma = %s
            """, (data_aula, id_t_filtro), fetch=True)
            
            total_p = len(presentes_detalhes) if presentes_detalhes else 0
            
            st.markdown(f"#### 🥋 Alunos no Tatame - {data_br} (Total: {total_p})")
            
            if presentes_detalhes:
                cores_map = {
                    'Branca': ('#FFFFFF', '#000000'), 'Cinza': ('#808080', '#FFFFFF'),
                    'Amarela': ('#FFFF00', '#000000'), 'Laranja': ('#FFA500', '#000000'),
                    'Verde': ('#008000', '#FFFFFF'), 'Azul': ('#0000FF', '#FFFFFF'),
                    'Roxa': ('#8A2BE2', '#FFFFFF'), 'Marrom': ('#8B4513', '#FFFFFF'),
                    'Preta': ('#000000', '#FFFFFF')
                }
                html_badges = '<div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:flex-start;align-items:center;width:100%;">'
                for p in presentes_detalhes:
                    bg, txt = cores_map.get(p['faixa'], ('#333333', '#FFFFFF'))
                    html_badges += f'<div style="background-color:{bg};color:{txt};padding:5px 14px;border-radius:18px;border:1px solid #555;font-size:13px;font-weight:500;white-space:nowrap;margin-bottom:4px;">{p["nome_completo"].strip()}</div>'
                html_badges += '</div>'
                st.markdown(html_badges, unsafe_allow_html=True)
            else:
                st.caption("Nenhum aluno confirmado nesta turma.")

    # =======================================================
    # 4. GRADUAÇÕES (FLUXO KANBAN COMPLETO)
    # =======================================================
    elif menu_selecionado == "🎓 Graduações":
        st.title("🎓 Gestão de Graduações")
        
        todas_solic = db.executar_query("""
            SELECT s.id, u.id as id_aluno, u.nome_completo, s.faixa_atual, s.nova_faixa, s.status 
            FROM solicitacoes_graduacao s 
            JOIN usuarios u ON s.id_aluno=u.id 
            WHERE s.id_filial=%s AND s.status IN ('Pendente', 'Aceito', 'Realizado')
            AND s.id IN (
                SELECT MAX(id) FROM solicitacoes_graduacao 
                WHERE status IN ('Pendente', 'Aceito', 'Realizado') 
                GROUP BY id_aluno
            )
        """, (id_filial,), fetch=True)
        
        mapa_status_solic = {s['id_aluno']: s['status'] for s in todas_solic} if todas_solic else {}
        
        col_fase2, col_fase3 = st.columns(2)
        
        # FASE 2: Aceite da Gestão (Somente Admins)
        if eh_admin:
            pendentes = [s for s in todas_solic if s['status'] == 'Pendente']
            with col_fase2:
                with st.expander(f"🟡 Novas Indicações ({len(pendentes)})", expanded=True):
                    if pendentes:
                        for p in pendentes:
                            with st.container(border=True):
                                st.write(f"**{p['nome_completo'].strip()}**")
                                faixa_at = p.get('faixa_atual') or 'Indefinida'
                                st.caption(f"Atual: {faixa_at}")
                                
                                # NOVO: Botões Lado a Lado (Aceitar / Recusar)
                                c_btn_acc, c_btn_rec = st.columns(2)
                                if c_btn_acc.button("✅ Aceitar", key=f"aceit_{p['id']}", type="primary", use_container_width=True):
                                    db.executar_query("UPDATE solicitacoes_graduacao SET status='Aceito' WHERE id=%s", (p['id'],))
                                    st.success("Liberado para exame!")
                                    time.sleep(0.5)
                                    st.rerun()
                                if c_btn_rec.button("❌ Recusar", key=f"recusa_{p['id']}", use_container_width=True):
                                    db.executar_query("DELETE FROM solicitacoes_graduacao WHERE id=%s", (p['id'],))
                                    st.warning("Indicação removida!")
                                    time.sleep(0.5)
                                    st.rerun()
                    else:
                        st.caption("Nenhuma indicação pendente.")
        
        # FASE 3: Lançar Resultados
        aceitos = [s for s in todas_solic if s['status'] == 'Aceito']
        with col_fase3 if eh_admin else st.container():
            with st.expander(f"🔵 Exames Agendados ({len(aceitos)})", expanded=True):
                if aceitos:
                    lista_cores = ["Cinza/Branca", "Cinza", "Cinza/Preta", "Amarela/Branca", "Amarela", "Amarela/Preta", 
                                   "Laranja/Branca", "Laranja", "Laranja/Preta", "Verde/Branca", "Verde", "Verde/Preta", 
                                   "Azul", "Roxa", "Marrom", "Preta"]
                    for a in aceitos:
                        with st.container(border=True):
                            st.write(f"**{a['nome_completo'].strip()}**")
                            faixa_at_a = a.get('faixa_atual') or 'Indefinida'
                            st.caption(f"De: {faixa_at_a}")
                            with st.form(key=f"form_result_{a['id']}"):
                                nova_cor = st.selectbox("Faixa Conquistada:", lista_cores)
                                
                                # NOVO: Botões Lado a Lado no Form (Lançar / Cancelar)
                                col_b1, col_b2 = st.columns(2)
                                if col_b1.form_submit_button("Lançar Resultado", type="primary", use_container_width=True):
                                    db.executar_query("UPDATE solicitacoes_graduacao SET nova_faixa=%s, status='Realizado' WHERE id=%s", (nova_cor, a['id']))
                                    st.success("Resultado enviado para homologação final!")
                                    time.sleep(1)
                                    st.rerun()
                                if col_b2.form_submit_button("❌ Cancelar", use_container_width=True):
                                    db.executar_query("DELETE FROM solicitacoes_graduacao WHERE id=%s", (a['id'],))
                                    st.warning("Exame cancelado e removido do painel!")
                                    time.sleep(1)
                                    st.rerun()
                else:
                    st.caption("Nenhum exame agendado.")
        
        st.divider()

        st.subheader("📡 Radar de Evolução")
        c_r1, c_r2 = st.columns(2)
        cat_radar = c_r1.radio("Público:", ["Adultos (16+)", "Kids (<16)"], horizontal=True)
        
        filtro_idade = ">= 16" if "Adultos" in cat_radar else "< 16"
        
        alunos_radar = db.executar_query(f"""
            SELECT id, nome_completo, faixa, graus, data_nascimento, data_ultimo_grau, data_inicio 
            FROM usuarios 
            WHERE id_filial=%s 
            AND status_conta='Ativo' 
            AND perfil='aluno'
            AND EXTRACT(YEAR FROM age(CURRENT_DATE, data_nascimento)) {filtro_idade}
            ORDER BY nome_completo
        """, (id_filial,), fetch=True)

        if alunos_radar:
            res_lote = db.executar_query("""
                SELECT p.id_aluno, COUNT(p.id) as total 
                FROM presencas p
                JOIN usuarios u ON p.id_aluno = u.id
                WHERE p.data_presenca > COALESCE(u.data_ultimo_grau, u.data_inicio)
                GROUP BY p.id_aluno
            """, fetch=True)
            
            mapa_presencas = {r['id_aluno']: r['total'] for r in res_lote} if res_lote else {}

            cols_rad = st.columns(4)
            for i, a in enumerate(alunos_radar):
                total_p = mapa_presencas.get(a['id'], 0)
                apto, msg, troca = utils.calcular_status_graduacao(a, total_p)
                
                with cols_rad[i % 4]:
                    with st.container(border=True):
                        st.markdown(f"**{a['nome_completo'].strip()}**")
                        st.caption(f"{a['faixa']} ({a['graus']}º G)")
                        
                        if a['id'] in mapa_status_solic:
                            status_atual = mapa_status_solic[a['id']]
                            if status_atual == 'Pendente':
                                st.markdown("**Status:** :orange[⏳ Aguardando Gestão]")
                                st.button("Indicação Enviada", key=f"sol_ok_{a['id']}", disabled=True, use_container_width=True)
                            elif status_atual == 'Aceito':
                                st.markdown("**Status:** :blue[📋 Confirmado(a) no Exame]")
                                st.button("Aguardando Teste", key=f"sol_ok_{a['id']}", disabled=True, use_container_width=True)
                            elif status_atual == 'Realizado':
                                st.markdown("**Status:** :green[✅ Aguardando Diploma]")
                                st.button("Aprovado!", key=f"sol_ok_{a['id']}", disabled=True, use_container_width=True)
                        else:
                            cor_texto = 'green' if apto else 'orange'
                            icone = "🔥" if (apto and troca) else ("🎓" if apto else "⏳")
                            st.markdown(f"**Status:** :{cor_texto}[{icone} {msg}]")
                            
                            if apto:
                                if troca:
                                    if st.button("Indicar Faixa", key=f"sol_{a['id']}", use_container_width=True, type="primary"):
                                        db.executar_query("""
                                            INSERT INTO solicitacoes_graduacao (id_aluno, id_filial, faixa_atual, nova_faixa, status)
                                            VALUES (%s, %s, %s, 'A Definir', 'Pendente')
                                        """, (a['id'], id_filial, a['faixa']))
                                        st.success("Indicação enviada!")
                                        time.sleep(1)
                                        st.rerun()
                                else:
                                    if st.button("Conceder Grau", key=f"g_adm_{a['id']}", use_container_width=True, type="primary"):
                                        db.registrar_grau_direto(a['id'])
                                        st.balloons()
                                        st.success(f"Grau concedido!")
                                        time.sleep(1)
                                        st.rerun()
        else:
            st.info("Nenhum aluno nesta categoria no momento.")

    # =======================================================
    # 5. TURMAS (CONFIGURAÇÃO + GESTÃO DE ELENCO)
    # =======================================================
    elif menu_selecionado == "📅 Turmas":
        st.title("📅 Gestão de Turmas")
        
        tab_config, tab_elenco = st.tabs(["⚙️ Criar/Editar Turmas", "👥 Alunos na Turma"])
        
        with tab_config:
            if 'edit_turma_id' not in st.session_state: 
                st.session_state.edit_turma_id = None

            v_n, v_d, v_h, v_p, v_m = "", "", "", None, None
            lbl_b = "➕ Criar Nova Turma"
            expandido = False
            
            if st.session_state.edit_turma_id:
                d_t = db.executar_query("SELECT * FROM turmas WHERE id=%s", (st.session_state.edit_turma_id,), fetch=True)[0]
                v_n, v_d, v_h, v_p, v_m = d_t['nome'], d_t['dias'], d_t['horario'], d_t['id_professor'], d_t['id_monitor']
                lbl_b = "💾 Salvar Alterações"
                expandido = True
            
            with st.expander(f"{'✏️ Editando Turma' if st.session_state.edit_turma_id else '➕ Adicionar Nova Turma'}", expanded=expandido):
                with st.form("form_turma"):
                    c1, c2, c3 = st.columns(3)
                    nome_t = c1.text_input("Nome da Turma", value=v_n, placeholder="Ex: Kids, Adulto...")
                    dias_t = c2.text_input("Dias", value=v_d, placeholder="Ex: Seg/Qua/Sex")
                    hora_t = c3.text_input("Horário", value=v_h, placeholder="Ex: 19:30")
                    
                    cp, cm = st.columns(2)
                    profs = db.executar_query("SELECT id, nome_completo FROM usuarios WHERE id_filial=%s AND perfil IN ('professor', 'lider', 'adm_filial') AND status_conta='Ativo'", (id_filial,), fetch=True)
                    opt_p = {p['nome_completo']: p['id'] for p in profs} if profs else {}
                    idx_p = list(opt_p.values()).index(v_p) if v_p in opt_p.values() else 0
                    sel_p = cp.selectbox("Professor Responsável", list(opt_p.keys()), index=idx_p) if opt_p else None
                    
                    mons = db.executar_query("SELECT id, nome_completo FROM usuarios WHERE id_filial=%s AND perfil='monitor' AND status_conta='Ativo'", (id_filial,), fetch=True)
                    opt_m = {"--- Sem Monitor ---": None}
                    if mons: opt_m.update({m['nome_completo']: m['id'] for m in mons})
                    idx_m = list(opt_m.values()).index(v_m) if v_m in opt_m.values() else 0
                    sel_m = cm.selectbox("Monitor Auxiliar", list(opt_m.keys()), index=idx_m)
                    
                    btn_col1, btn_col2 = st.columns([1, 4])
                    if btn_col1.form_submit_button(lbl_b, type="primary"):
                        if nome_t and dias_t and hora_t and sel_p:
                            id_p_db = opt_p[sel_p]
                            id_m_db = opt_m[sel_m]
                            if st.session_state.edit_turma_id:
                                db.executar_query("UPDATE turmas SET nome=%s, dias=%s, horario=%s, id_professor=%s, id_monitor=%s WHERE id=%s", 
                                                 (nome_t, dias_t, hora_t, id_p_db, id_m_db, st.session_state.edit_turma_id))
                                st.session_state.edit_turma_id = None
                                st.success("Turma atualizada!")
                            else:
                                db.executar_query("INSERT INTO turmas (nome, dias, horario, id_professor, id_monitor, id_filial) VALUES (%s, %s, %s, %s, %s, %s)", 
                                                 (nome_t, dias_t, hora_t, id_p_db, id_m_db, id_filial))
                                st.success("Turma criada!")
                            time.sleep(1); st.rerun()
                        else: st.error("Preencha todos os campos obrigatórios.")
                    
                    if st.session_state.edit_turma_id:
                        if btn_col2.form_submit_button("❌ Cancelar"):
                            st.session_state.edit_turma_id = None; st.rerun()

            st.write("")
            st.markdown("##### 📍 Turmas Ativas")
            
            q_ts = """
                SELECT t.id, t.nome, t.dias, t.horario, u1.nome_completo as prof, u2.nome_completo as mon,
                (SELECT COUNT(*) FROM usuarios WHERE id_turma = t.id AND status_conta = 'Ativo') as total
                FROM turmas t
                LEFT JOIN usuarios u1 ON t.id_professor = u1.id
                LEFT JOIN usuarios u2 ON t.id_monitor = u2.id
                WHERE t.id_filial=%s ORDER BY t.horario
            """
            ts_list = db.executar_query(q_ts, (id_filial,), fetch=True)
            
            if ts_list:
                c_list = st.columns(2)
                for idx, t in enumerate(ts_list):
                    with c_list[idx % 2]:
                        with st.container(border=True):
                            st.markdown(f"**{t['nome']}** - {t['horario']}")
                            st.caption(f"📅 {t['dias']} | 👥 {t['total']} Alunos")
                            st.write(f"🥋 Prof. {t['prof'] or 'Não definido'}")
                            if t['mon']: st.caption(f"辅助 Monitor: {t['mon']}")
                            
                            c_btn1, c_btn2 = st.columns(2)
                            if c_btn1.button("✏️ Editar", key=f"edit_t_{t['id']}", use_container_width=True):
                                st.session_state.edit_turma_id = t['id']; st.rerun()
                            if c_btn2.button("🗑️ Excluir", key=f"del_t_{t['id']}", use_container_width=True):
                                db.executar_query("DELETE FROM turmas WHERE id=%s", (t['id'],)); st.rerun()
            else: st.info("Nenhuma turma cadastrada.")

        with tab_elenco:
            st.markdown("##### 👥 Organizar Alunos")
            t_gestao = db.executar_query("SELECT id, nome, horario FROM turmas WHERE id_filial=%s ORDER BY horario", (id_filial,), fetch=True)
            d_t_gestao = {f"{t['nome']} ({t['horario']})": t['id'] for t in t_gestao} if t_gestao else {}
            
            sel_t = st.selectbox("Selecione a Turma alvo:", list(d_t_gestao.keys()), key="gestao_elenco_sel")
            
            if sel_t:
                id_t_alvo = d_t_gestao[sel_t]
                col_dentro, col_fora = st.columns(2, gap="medium")
                
                with col_dentro:
                    st.success(f"Alunos em {sel_t}")
                    al_dentro = db.executar_query("SELECT id, nome_completo FROM usuarios WHERE id_turma=%s AND status_conta='Ativo' ORDER BY nome_completo", (id_t_alvo,), fetch=True)
                    if al_dentro:
                        for a in al_dentro:
                            if st.button(f"❌ {a['nome_completo'].strip()}", key=f"rem_al_{a['id']}", use_container_width=True, help="Remover da turma"):
                                db.executar_query("UPDATE usuarios SET id_turma=NULL WHERE id=%s", (a['id'],)); st.rerun()
                    else: st.caption("Turma vazia.")

                with col_fora:
                    st.warning("Alunos aguardando turma")
                    al_fora = db.executar_query("SELECT id, nome_completo FROM usuarios WHERE id_turma IS NULL AND id_filial=%s AND status_conta='Ativo' AND perfil IN ('aluno', 'monitor') ORDER BY nome_completo", (id_filial,), fetch=True)
                    if al_fora:
                        for a in al_fora:
                            if st.button(f"➕ {a['nome_completo'].strip()}", key=f"add_al_{a['id']}", use_container_width=True, help="Adicionar à turma"):
                                db.executar_query("UPDATE usuarios SET id_turma=%s WHERE id=%s", (id_t_alvo, a['id'])); st.rerun()
                    else: st.caption("Não há alunos sem turma.")

    # =======================================================
    # 6. GESTÃO DE ALUNOS
    # =======================================================
    elif menu_selecionado == "👥 Alunos":
        st.title("👥 Gestão de Alunos")

        with st.container(border=True):
            c_busca, c_turma, c_status = st.columns([2, 1, 1])
            busca_nome = c_busca.text_input("🔍 Buscar por nome...", placeholder="Digite o nome do aluno")
            
            turmas_f = db.executar_query("SELECT id, nome, horario FROM turmas WHERE id_filial=%s ORDER BY horario", (id_filial,), fetch=True)
            d_tf = {f"{t['nome']} ({t['horario']})": t['id'] for t in turmas_f} if turmas_f else {}
            
            sel_tf = c_turma.selectbox("📍 Filtrar Turma", ["Todas"] + list(d_tf.keys()))
            filtro_status = c_status.selectbox("📌 Status", ["Ativo", "Inativo", "Todos"], index=0)

        if st.session_state.get('aluno_edit_id'):
            id_ed = st.session_state['aluno_edit_id']
            dados_al = db.executar_query("SELECT * FROM usuarios WHERE id=%s", (id_ed,), fetch=True)
            
            if dados_al:
                al_dados = dados_al[0]
                with st.container(border=True):
                    st.subheader(f"📝 Editando Perfil: {al_dados['nome_completo'].strip()}")
                    with st.form("form_edicao_aluno_completo"):
                        c1, c2, c3 = st.columns([2, 1, 1])
                        novo_nome = c1.text_input("Nome Completo", value=al_dados['nome_completo'].strip())
                        novo_email = c2.text_input("E-mail (Login)", value=al_dados['email'])
                        novo_tel = c3.text_input("Telefone", value=al_dados['telefone'])
                        
                        c4, c5, c6, c7 = st.columns(4)
                        lista_faixas = ["Branca", "Cinza", "Amarela", "Laranja", "Verde", "Azul", "Roxa", "Marrom", "Preta"]
                        idx_f = lista_faixas.index(al_dados['faixa']) if al_dados['faixa'] in lista_faixas else 0
                        nova_faixa = c4.selectbox("Faixa Atual", lista_faixas, index=idx_f)
                        
                        novo_grau = c5.number_input("Graus", min_value=0, max_value=11, value=int(al_dados['graus'] or 0))
                        nova_nasc = c6.date_input("Data Nascimento", value=al_dados['data_nascimento'], format="DD/MM/YYYY")
                        
                        turmas_list = list(d_tf.keys())
                        nome_t_atual = [nome for nome, id_t in d_tf.items() if id_t == al_dados['id_turma']]
                        idx_t = turmas_list.index(nome_t_atual[0]) if nome_t_atual else 0
                        nova_turma = c7.selectbox("Turma Fixa", turmas_list, index=idx_t)
                        
                        st.write("")
                        cb1, cb2 = st.columns(2)
                        if cb1.form_submit_button("💾 Salvar Todas as Alterações", type="primary", use_container_width=True):
                            db.executar_query("""
                                UPDATE usuarios 
                                SET nome_completo=%s, email=%s, telefone=%s, faixa=%s, graus=%s, data_nascimento=%s, id_turma=%s 
                                WHERE id=%s
                            """, (novo_nome, novo_email, novo_tel, nova_faixa, novo_grau, nova_nasc, d_tf.get(nova_turma), id_ed))
                            
                            st.session_state['aluno_edit_id'] = None
                            st.success("Cadastro atualizado!")
                            time.sleep(0.5)
                            st.rerun()
                            
                        if cb2.form_submit_button("❌ Cancelar", use_container_width=True):
                            st.session_state['aluno_edit_id'] = None
                            st.rerun()
                st.divider()

        if st.session_state.get('promover_cargo_id'):
            id_p = st.session_state['promover_cargo_id']
            al_p = db.executar_query("SELECT nome_completo, perfil FROM usuarios WHERE id=%s", (id_p,), fetch=True)[0]
            with st.container(border=True):
                st.warning(f"Alterar cargo de {al_p['nome_completo'].strip()}?")
                n_perfil = st.selectbox("Novo Perfil:", ["aluno", "monitor", "professor"], index=0)
                cp1, cp2 = st.columns(2)
                if cp1.button("Confirmar Promoção", type="primary", use_container_width=True):
                    db.executar_query("UPDATE usuarios SET perfil=%s WHERE id=%s", (n_perfil, id_p))
                    st.session_state['promover_cargo_id'] = None
                    st.success("Cargo atualizado!")
                    time.sleep(0.5); st.rerun()
                if cp2.button("Desistir", use_container_width=True):
                    st.session_state['promover_cargo_id'] = None
                    st.rerun()
            st.divider()

        sql_alunos = """
            SELECT u.*, t.nome as nome_turma, t.horario as horario_turma
            FROM usuarios u
            LEFT JOIN turmas t ON u.id_turma = t.id
            WHERE u.id_filial = %s AND u.perfil IN ('aluno', 'monitor', 'professor')
        """
        params = [id_filial]

        if busca_nome:
            sql_alunos += " AND u.nome_completo ILIKE %s"
            params.append(f"%{busca_nome}%")
        if sel_tf != "Todas":
            sql_alunos += " AND u.id_turma = %s"
            params.append(d_tf[sel_tf])
        if filtro_status != "Todos":
            sql_alunos += " AND u.status_conta = %s"
            params.append(filtro_status)

        sql_alunos += " ORDER BY u.nome_completo ASC"
        alunos = db.executar_query(sql_alunos, tuple(params), fetch=True)

        if alunos:
            st.caption(f"Exibindo {len(alunos)} membros")
            cols_lista = st.columns(2)
            
            for idx, al in enumerate(alunos):
                with cols_lista[idx % 2]:
                    with st.container(border=True):
                        c_h, c_b = st.columns([1.8, 1.2])
                        cor_st = "green" if al['status_conta'] == 'Ativo' else "red"
                        cargo = f" | {al['perfil'].upper()}" if al['perfil'] != 'aluno' else ""
                        c_h.markdown(f"{al['nome_completo'].strip()}{cargo} <span style='color:{cor_st}; font-size:10px;'>● {al['status_conta']}</span>", unsafe_allow_html=True)
                        
                        with c_b:
                            bz, be, bu, bs = st.columns(4)
                            tel_l = ''.join(filter(str.isdigit, str(al['telefone'] or "")))
                            bz.markdown(f"[💬](https://wa.me/55{tel_l})" if tel_l else "🚫", help="WhatsApp")
                            
                            if be.button("📝", key=f"btn_ed_{al['id']}", help="Editar"):
                                st.session_state['aluno_edit_id'] = al['id']
                                st.rerun()
                            
                            if bu.button("🆙", key=f"btn_up_{al['id']}", help="Cargos"):
                                st.session_state['promover_cargo_id'] = al['id']
                                st.rerun()

                            if bs.button("🔄", key=f"btn_st_{al['id']}", help="Status"):
                                n_st = "Inativo" if al['status_conta'] == "Ativo" else "Ativo"
                                db.executar_query("UPDATE usuarios SET status_conta=%s WHERE id=%s", (n_st, al['id']))
                                st.rerun()

                        dt_nasc = al['data_nascimento'].strftime('%d/%m/%Y') if al['data_nascimento'] else "--/--/----"
                        st.caption(f"🥋 {al['faixa']} - {al['graus']}º G | 🎂 {dt_nasc} | 📍 {al['nome_turma']}")

                        with st.expander("📊 Ver Histórico e Presenças"):
                            t_g, t_p = st.columns(2)
                            
                            with t_g:
                                st.markdown("🎓 Graduações")
                                h_g = db.executar_query("""
                                    SELECT faixa, data_graduacao 
                                    FROM historico_graduacoes WHERE id_aluno=%s 
                                    ORDER BY data_graduacao DESC LIMIT 3
                                """, (al['id'],), fetch=True)
                                if h_g:
                                    for g in h_g: 
                                        st.write(f"• {g['faixa']} ({g['data_graduacao'].strftime('%d/%m/%Y')})")
                                else: st.caption("Sem histórico registrado.")

                            with t_p:
                                st.markdown("📅 Frequência")
                                p1 = db.executar_query("SELECT COUNT(*) as total FROM presencas WHERE id_aluno=%s AND EXTRACT(MONTH FROM data_presenca) = EXTRACT(MONTH FROM CURRENT_DATE) AND EXTRACT(YEAR FROM data_presenca) = EXTRACT(YEAR FROM CURRENT_DATE)", (al['id'],), fetch=True)
                                p2 = db.executar_query("SELECT COUNT(*) as total FROM presencas WHERE id_aluno=%s AND EXTRACT(MONTH FROM data_presenca) = EXTRACT(MONTH FROM CURRENT_DATE - INTERVAL '1 month') AND EXTRACT(YEAR FROM data_presenca) = EXTRACT(YEAR FROM CURRENT_DATE - INTERVAL '1 month')", (al['id'],), fetch=True)
                                
                                cm1, cm2 = st.columns(2)
                                cm1.metric("Atual", p1[0]['total'] if p1 else 0)
                                cm2.metric("Anterior", p2[0]['total'] if p2 else 0)
        else:
            st.warning("Nenhum membro encontrado.")

    # =======================================================
    # 7. RANKING "CASCA GROSSA"
    # =======================================================
    elif "Ranking" in menu_selecionado:
        st.title("🏆 Rankings e Conquistas")

        with st.container(border=True):
            c_cat, _ = st.columns([2, 1])
            categoria_ranking = c_cat.radio("Selecione a Categoria:", ["🥋 Adultos (16+)", "🧒 Kids (até 15)"], horizontal=True)
            
            if "Adultos" in categoria_ranking:
                filtro_idade_sql = "AND EXTRACT(YEAR FROM age(CURRENT_DATE, u.data_nascimento)) >= 16"
            else:
                filtro_idade_sql = "AND EXTRACT(YEAR FROM age(CURRENT_DATE, u.data_nascimento)) < 16"

        st.markdown(f"### 🦍 Ranking Casca Grossa (Mês) - {categoria_ranking.split(' ')[1]}")
        
        sql_mes = f"""
            SELECT u.nome_completo, u.faixa, COUNT(p.id) as treinos
            FROM presencas p 
            INNER JOIN usuarios u ON p.id_aluno = u.id
            WHERE u.id_filial = %s 
              AND EXTRACT(MONTH FROM p.data_presenca) = %s 
              AND EXTRACT(YEAR FROM p.data_presenca) = %s
              {filtro_idade_sql}
            GROUP BY u.nome_completo, u.faixa 
            ORDER BY treinos DESC, u.nome_completo ASC
        """
        rank_mes = db.executar_query(sql_mes, (id_filial, date.today().month, date.today().year), fetch=True)

        if rank_mes:
            cols_p = st.columns(3)
            medalhas_p = [("🥇 1º", "#FFD700"), ("🥈 2º", "#C0C0C0"), ("🥉 3º", "#CD7F32")]
            for i in range(min(3, len(rank_mes))):
                with cols_p[i]:
                    with st.container(border=True):
                        label, cor = medalhas_p[i]
                        st.markdown(f"<h4 style='text-align:center; color:{cor}; margin:0;'>{label}</h4>", unsafe_allow_html=True)
                        st.markdown(f"<p style='text-align:center; font-weight:bold; margin:0;'>{rank_mes[i]['nome_completo'].strip()}</p>", unsafe_allow_html=True)
                        st.markdown(f"**{rank_mes[i]['treinos']} treinos**", help="Total do mês")
            
            if len(rank_mes) > 3:
                with st.expander("Ver classificação completa"):
                    st.dataframe(pd.DataFrame(rank_mes[3:], columns=['nome_completo', 'faixa', 'treinos']), use_container_width=True)
        else:
            st.info("Nenhum treino registrado nesta categoria este mês.")

        st.divider()

        st.markdown(f"### 🏅 Quadro de Medalhas - {categoria_ranking.split(' ')[1]}")
        col_medalhas, col_lancar = st.columns([1.5, 1])

        with col_medalhas:
            sql_comp = f"""
                SELECT u.nome_completo, SUM(hc.pontos) as total
                FROM historico_competicoes hc 
                INNER JOIN usuarios u ON hc.id_aluno = u.id
                WHERE u.id_filial = %s AND hc.status = 'Aprovado' 
                  AND EXTRACT(YEAR FROM hc.data_competicao) = %s
                  {filtro_idade_sql}
                GROUP BY u.nome_completo ORDER BY total DESC
            """
            rank_comp = db.executar_query(sql_comp, (id_filial, date.today().year), fetch=True)
            
            if rank_comp:
                for rc in rank_comp:
                    with st.container(border=True):
                        c_n, c_p = st.columns([3, 1])
                        c_n.write(f"🏆 {rc['nome_completo'].strip()}")
                        c_p.markdown(f"**{rc['total']} pts**")
            else:
                st.info("Sem medalhas aprovadas este ano.")

            med_pend = db.executar_query(f"""
                SELECT h.id, u.nome_completo, h.nome_campeonato, h.medalha
                FROM historico_competicoes h 
                INNER JOIN usuarios u ON h.id_aluno = u.id
                WHERE u.id_filial = %s AND h.status = 'Pendente' {filtro_idade_sql}
            """, (id_filial,), fetch=True)
            
            if med_pend:
                st.warning(f"🔔 {len(med_pend)} Medalhas para Aprovar")
                for mp in med_pend:
                    with st.container(border=True):
                        st.write(f"{mp['nome_completo'].strip()} - {mp['medalha']}")
                        st.caption(f"Torneio: {mp['nome_campeonato']}")
                        b1, b2 = st.columns(2)
                        if b1.button("✅ Sim", key=f"acc_{mp['id']}"):
                            db.executar_query("UPDATE historico_competicoes SET status='Aprovado' WHERE id=%s", (mp['id'],))
                            st.rerun()
                        if b2.button("❌ Não", key=f"rec_{mp['id']}"):
                            db.executar_query("UPDATE historico_competicoes SET status='Recusado' WHERE id=%s", (mp['id'],))
                            st.rerun()

        with col_lancar:
            with st.container(border=True):
                st.markdown("##### 🏅 Lançar Medalha")
                sql_lista_alunos = f"""
                    SELECT u.id, u.nome_completo 
                    FROM usuarios u 
                    WHERE u.id_filial = %s AND u.status_conta = 'Ativo' {filtro_idade_sql} 
                    ORDER BY u.nome_completo
                """
                alunos_f = db.executar_query(sql_lista_alunos, (id_filial,), fetch=True)
                opts_al = {al['nome_completo'].strip(): al['id'] for al in alunos_f} if alunos_f else {}
                
                with st.form("form_medalha_adm", clear_on_submit=True):
                    al_sel = st.selectbox("Atleta", list(opts_al.keys())) if opts_al else None
                    med_tipo = st.selectbox("Medalha", ["Ouro", "Prata", "Bronze", "Participação"])
                    torneio = st.text_input("Campeonato")
                    if st.form_submit_button("Registrar Conquista", use_container_width=True, type="primary"):
                        if al_sel and torneio:
                            pts = {"Ouro": 9, "Prata": 3, "Bronze": 1, "Participação": 0.5}[med_tipo]
                            db.executar_query("""
                                INSERT INTO historico_competicoes (id_aluno, id_filial, nome_campeonato, medalha, pontos, status, data_competicao) 
                                VALUES (%s, %s, %s, %s, %s, 'Aprovado', CURRENT_DATE)
                            """, (opts_al[al_sel], id_filial, torneio, med_tipo, pts))
                            st.success("🏅 Medalha registrada!")
                            time.sleep(1); st.rerun()