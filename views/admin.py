import streamlit as st
import database as db
import utils
import time
import pandas as pd
import plotly.express as px
from datetime import date

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

    tab_dash, tab_chamada, tab_grad, tab_turmas, tab_alunos = st.tabs(["📊 Painel", "✅ Chamada", "🎓 Graduações", "📅 Turmas", "👥 Alunos"])

    # =======================================================
    # 1. DASHBOARD
    # =======================================================
    with tab_dash:
        avisos = db.executar_query("""
            SELECT titulo, mensagem, data_postagem FROM avisos 
            WHERE ativo=TRUE 
            AND publico_alvo IN ('Todos', 'Admins Filiais', 'Professores') 
            ORDER BY id DESC
        """, fetch=True)
        
        if avisos:
            with st.expander("📢 Mural de Avisos", expanded=True):
                for av in avisos:
                    st.info(f"**{av['titulo']}** ({av['data_postagem'].strftime('%d/%m')})\n\n{av['mensagem']}")
        
        st.write("")

        qtd_alunos = db.executar_query("SELECT COUNT(*) FROM usuarios WHERE id_filial=%s AND status_conta='Ativo' AND perfil='aluno'", (id_filial,), fetch=True)[0][0]
        treinos_hoje = db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_filial=%s AND data_aula=CURRENT_DATE", (id_filial,), fetch=True)[0][0]
        
        q_niver = """
            SELECT nome_completo, telefone FROM usuarios 
            WHERE id_filial=%s AND status_conta='Ativo' 
            AND EXTRACT(MONTH FROM data_nascimento) = EXTRACT(MONTH FROM CURRENT_DATE)
            AND EXTRACT(DAY FROM data_nascimento) = EXTRACT(DAY FROM CURRENT_DATE)
        """
        aniversariantes = db.executar_query(q_niver, (id_filial,), fetch=True)
        qtd_niver = len(aniversariantes) if aniversariantes else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Alunos Ativos", qtd_alunos)
        c2.metric("Treinos Hoje", treinos_hoje)
        label_niver = "🎂 Niver Hoje" if qtd_niver == 0 else "🎉 Hoje tem Festa!"
        c3.metric(label_niver, qtd_niver)
        
        st.divider()

        if qtd_niver > 0:
            st.success(f"🎈 **{qtd_niver} Aniversariante(s) hoje!**")
            st.dataframe(pd.DataFrame(aniversariantes, columns=['Nome', 'WhatsApp']), use_container_width=True, hide_index=True)
            st.divider()

        d_faixa = db.executar_query("SELECT faixa, COUNT(*) as qtd FROM usuarios WHERE id_filial=%s AND perfil='aluno' AND status_conta='Ativo' GROUP BY faixa", (id_filial,), fetch=True)
        
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
                fig_bar.update_traces(textposition='outside')
                fig_bar.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_bar, use_container_width=True)

    # =======================================================
    # 2. CHAMADA
    # =======================================================
    with tab_chamada:
        col_lista, col_filtros = st.columns([3, 1.2])
        
        with col_filtros:
            with st.container(border=True):
                st.markdown("#### ⚙️ Configuração")
                data_aula = st.date_input("📅 Data da Aula", value=date.today())
                turmas = db.executar_query("SELECT id, nome, horario FROM turmas WHERE id_filial=%s", (id_filial,), fetch=True)
                d_t = {f"{t['nome']} ({t['horario']})": t['id'] for t in turmas} if turmas else {}
                sel_turma = st.selectbox("Selecione a Turma", list(d_t.keys())) if d_t else None
                metric_ph = st.empty()

        with col_lista:
            if sel_turma:
                id_t = d_t[sel_turma]
                alunos = db.executar_query("SELECT id, nome_completo, faixa FROM usuarios WHERE id_turma=%s AND status_conta='Ativo' ORDER BY nome_completo", (id_t,), fetch=True)
                checkins_feitos = [x[0] for x in db.executar_query("SELECT id_aluno FROM checkins WHERE id_turma=%s AND data_aula=%s", (id_t, data_aula), fetch=True)]
                
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
                    if st.form_submit_button("💾 Salvar / Atualizar Chamada", type="primary", use_container_width=True):
                        db.executar_query("DELETE FROM checkins WHERE id_turma=%s AND data_aula=%s", (id_t, data_aula))
                        count = 0
                        for uid in checks:
                            db.executar_query("INSERT INTO checkins (id_aluno, id_turma, id_filial, data_aula) VALUES (%s, %s, %s, %s)", (uid, id_t, id_filial, data_aula))
                            count += 1
                        st.toast(f"Chamada atualizada! {count} presentes.")
                        time.sleep(0.5)
                        st.rerun()
                
                qtd_total = len(alunos)
                qtd_pres = len(checkins_feitos)
                perc = int((qtd_pres/qtd_total)*100) if qtd_total > 0 else 0
                metric_ph.metric("Presença", f"{qtd_pres}/{qtd_total}", f"{perc}%")

            else:
                st.info("Cadastre uma turma na aba 'Turmas' para começar.")

        st.divider()
        if sel_turma and checkins_feitos:
            st.markdown("#### ✅ Alunos Confirmados nesta Data:")
            nomes_presentes = db.executar_query("SELECT nome_completo, faixa FROM usuarios WHERE id IN %s", (tuple(checkins_feitos),), fetch=True) if checkins_feitos else []
            html_tags = ""
            cores_faixa = {'Branca': '#eee', 'Azul': '#cce5ff', 'Roxa': '#e2cfff', 'Marrom': '#e8dccc', 'Preta': '#333'}
            text_colors = {'Preta': 'white', 'Branca': 'black'}
            for p in nomes_presentes:
                bg = cores_faixa.get(p['faixa'], '#eee')
                txt = text_colors.get(p['faixa'], 'black')
                html_tags += f'<span style="background-color:{bg}; color:{txt}; padding:4px 10px; border-radius:15px; margin-right:5px; font-size:0.9em; display:inline-block; margin-bottom:5px;">{p["nome_completo"]}</span>'
            st.markdown(html_tags, unsafe_allow_html=True)

    # =======================================================
    # 3. GRADUAÇÃO
    # =======================================================
    with tab_grad:
        if eh_admin:
            pend = db.executar_query("SELECT s.id, u.nome_completo, s.nova_faixa FROM solicitacoes_graduacao s JOIN usuarios u ON s.id_aluno=u.id WHERE s.id_filial=%s AND s.status='Pendente'", (id_filial,), fetch=True)
            if pend:
                st.write("**Financeiro:**")
                for p in pend:
                    c1, c2 = st.columns([3,1])
                    c1.write(f"{p['nome_completo']} -> {p['nova_faixa']}")
                    if c2.button("Autorizar", key=f"au_{p['id']}"):
                        db.executar_query("UPDATE solicitacoes_graduacao SET status='Aguardando Exame' WHERE id=%s", (p['id'],))
                        st.rerun()
        
        exams = db.executar_query("SELECT s.id, u.nome_completo, s.nova_faixa FROM solicitacoes_graduacao s JOIN usuarios u ON s.id_aluno=u.id WHERE s.id_filial=%s AND s.status='Aguardando Exame'", (id_filial,), fetch=True)
        if exams:
            st.write("**Exame Prático:**")
            for e in exams:
                c1, c2 = st.columns([3,1])
                c1.write(f"{e['nome_completo']} -> {e['nova_faixa']}")
                if c2.button("Aprovado", key=f"ex_{e['id']}"):
                    db.executar_query("UPDATE solicitacoes_graduacao SET status='Aguardando Homologacao' WHERE id=%s", (e['id'],))
                    st.rerun()

        st.divider()
        st.markdown("#### 📡 Radar")
        alunos = db.executar_query("SELECT id, nome_completo, faixa, graus, data_nascimento, data_ultimo_grau, data_inicio FROM usuarios WHERE id_filial=%s AND perfil='aluno' AND status_conta='Ativo'", (id_filial,), fetch=True)
        if alunos:
            for a in alunos:
                marco = a['data_ultimo_grau'] or a['data_inicio'] or date.today()
                pres = db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s AND data_aula >= %s", (a['id'], marco), fetch=True)[0][0]
                _, msg, prog, troca = utils.calcular_status_graduacao(a, pres)
                with st.expander(f"{'🔥' if prog >=1 else '⏳'} {a['nome_completo']} - {msg}"):
                    st.progress(prog)
                    c1, c2 = st.columns(2)
                    if c1.button("+1 Grau", key=f"g_{a['id']}"):
                        db.executar_query("UPDATE usuarios SET graus = graus + 1, data_ultimo_grau = CURRENT_DATE WHERE id=%s", (a['id'],))
                        st.toast("Grau +1"); st.rerun()
                    if troca:
                        nf = utils.get_proxima_faixa(a['faixa'])
                        if c2.button(f"Indicar {nf}", key=f"ind_{a['id']}"):
                            db.executar_query("INSERT INTO solicitacoes_graduacao (id_aluno, id_filial, faixa_atual, nova_faixa, status) VALUES (%s, %s, %s, %s, 'Pendente')", (a['id'], id_filial, a['faixa'], nf))
                            st.success("Indicado!"); st.rerun()

    # =======================================================
    # 4. TURMAS
    # =======================================================
    with tab_turmas:
        sub_tab_config, sub_tab_enturmar = st.tabs(["⚙️ Criar/Editar Turmas", "👥 Gerenciar Alunos na Turma"])

        with sub_tab_config:
            with st.container(border=True):
                st.markdown("##### Nova Turma")
                with st.form("nt"):
                    c_n, c_d, c_h = st.columns(3)
                    n = c_n.text_input("Nome (Ex: Kids)")
                    d = c_d.text_input("Dias (Ex: Seg/Qua)")
                    h = c_h.text_input("Horário (Ex: 19h)")
                    if st.form_submit_button("➕ Criar Turma"):
                        if n and d and h:
                            db.executar_query("INSERT INTO turmas (nome, dias, horario, responsavel, id_filial) VALUES (%s, %s, %s, '', %s)", (n, d, h, id_filial))
                            st.success("Turma criada!"); st.rerun()
                        else: st.error("Preencha tudo.")

            st.markdown("##### Turmas Ativas")
            ts = db.executar_query("SELECT id, nome, dias, horario FROM turmas WHERE id_filial=%s ORDER BY nome", (id_filial,), fetch=True)
            if ts:
                for t in ts:
                    qtd_t = db.executar_query("SELECT COUNT(*) FROM usuarios WHERE id_turma=%s AND status_conta='Ativo'", (t['id'],), fetch=True)[0][0]
                    with st.expander(f"🥋 {t['nome']} ({qtd_t} alunos)"):
                        c1, c2, c3 = st.columns([2, 2, 1])
                        c1.write(f"📅 **Dias:** {t['dias']}")
                        c2.write(f"⏰ **Horário:** {t['horario']}")
                        if c3.button("🗑️ Excluir", key=f"del_t_{t['id']}"):
                            if qtd_t > 0: st.error("Turma com alunos! Remova-os antes.")
                            else:
                                db.executar_query("DELETE FROM turmas WHERE id=%s", (t['id'],))
                                st.rerun()
            else: st.info("Nenhuma turma cadastrada.")

        with sub_tab_enturmar:
            st.markdown("##### Gestão de Elenco")
            d_turmas_sel = {f"{t['nome']} ({t['horario']})": t['id'] for t in ts} if ts else {}
            sel_t_gestao = st.selectbox("Selecione a Turma para Gerenciar", list(d_turmas_sel.keys())) if d_turmas_sel else None
            
            if sel_t_gestao:
                id_t_alvo = d_turmas_sel[sel_t_gestao]
                col_in, col_out = st.columns(2)
                
                with col_in:
                    st.success("✅ Alunos Nesta Turma")
                    alunos_in = db.executar_query("SELECT id, nome_completo, faixa FROM usuarios WHERE id_turma=%s AND status_conta='Ativo' ORDER BY nome_completo", (id_t_alvo,), fetch=True)
                    if alunos_in:
                        for a in alunos_in:
                            c_nome, c_btn = st.columns([0.8, 0.2])
                            c_nome.write(f"🥋 {a['nome_completo']}")
                            if c_btn.button("❌", key=f"rem_{a['id']}", help="Remover da turma"):
                                db.executar_query("UPDATE usuarios SET id_turma=NULL WHERE id=%s", (a['id'],))
                                st.toast("Aluno removido da turma!")
                                time.sleep(0.5); st.rerun()
                    else: st.caption("Nenhum aluno nesta turma.")

                with col_out:
                    st.warning("⚠️ Alunos Sem Turma / Disponíveis")
                    alunos_out = db.executar_query("SELECT id, nome_completo, faixa FROM usuarios WHERE (id_turma IS NULL OR id_turma != %s) AND id_filial=%s AND status_conta='Ativo' AND perfil='aluno' ORDER BY nome_completo", (id_t_alvo, id_filial), fetch=True)
                    filtro = st.text_input("🔎 Buscar aluno", placeholder="Nome...")
                    count_show = 0
                    for a in alunos_out:
                        if filtro.lower() in a['nome_completo'].lower():
                            c_nome, c_btn = st.columns([0.8, 0.2])
                            c_nome.write(f"{a['nome_completo']}")
                            if c_btn.button("➕", key=f"add_{a['id']}", help="Adicionar"):
                                db.executar_query("UPDATE usuarios SET id_turma=%s WHERE id=%s", (id_t_alvo, a['id']))
                                st.toast("Aluno adicionado!")
                                time.sleep(0.5); st.rerun()
                            count_show += 1
                            if count_show >= 10 and not filtro:
                                st.caption("... use a busca para ver mais.")
                                break

    # =======================================================
    # 5. ALUNOS (VISÃO COMPACTA)
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
                    if c_b2.form_submit_button("Cancelar", use_container_width=True):
                        st.session_state.aluno_edit_id = None; st.rerun()

        elif st.session_state.aluno_promo_id:
            st.warning("⭐ **Promover Aluno a Staff**")
            dados_promo = db.executar_query("SELECT nome_completo FROM usuarios WHERE id=%s", (st.session_state.aluno_promo_id,), fetch=True)[0]
            st.write(f"Você está promovendo **{dados_promo['nome_completo']}**.")
            
            with st.container(border=True):
                novo_cargo = st.selectbox("Selecione o Novo Cargo:", ["monitor", "professor"])
                c_p1, c_p2 = st.columns(2)
                if c_p1.button("✅ Confirmar", use_container_width=True):
                    db.executar_query("UPDATE usuarios SET perfil=%s WHERE id=%s", (novo_cargo, st.session_state.aluno_promo_id))
                    st.success(f"Promovido para {novo_cargo}!"); st.session_state.aluno_promo_id = None; time.sleep(1.5); st.rerun()
                if c_p2.button("Cancelar", use_container_width=True):
                    st.session_state.aluno_promo_id = None; st.rerun()

        else:
            tab_l, tab_n = st.tabs(["📋 Lista de Alunos", "➕ Matricular Novo"])
            
            with tab_l:
                c_h1, c_h2, c_h3 = st.columns([2, 1, 1.5])
                c_h1.markdown("**Nome**")
                c_h2.markdown("**Faixa**")
                c_h3.markdown("**Ações**")
                
                # Linha separadora inicial fina
                st.markdown('<hr style="margin: 5px 0; border: none; border-top: 1px solid #333;">', unsafe_allow_html=True)

                membros = db.executar_query("SELECT id, nome_completo, faixa FROM usuarios WHERE id_filial=%s AND status_conta='Ativo' AND perfil='aluno' ORDER BY nome_completo", (id_filial,), fetch=True)
                
                if membros:
                    for m in membros:
                        c1, c2, c3 = st.columns([2, 1, 1.5])
                        c1.write(f"{m['nome_completo']}")
                        c2.caption(f"{m['faixa']}")
                        
                        with c3:
                            b_ed, b_up, b_del = st.columns([1, 1, 1], gap="small")
                            
                            if b_ed.button("✏️", key=f"edt_{m['id']}", help="Editar"):
                                st.session_state.aluno_edit_id = m['id']
                                st.rerun()
                                
                            if b_up.button("⭐", key=f"prm_{m['id']}", help="Promover"):
                                st.session_state.aluno_promo_id = m['id']
                                st.rerun()
                                
                            if eh_admin:
                                if b_del.button("🗑️", key=f"del_{m['id']}", help="Excluir"):
                                    db.executar_query("UPDATE usuarios SET status_conta='Inativo' WHERE id=%s", (m['id'],))
                                    st.toast("Aluno inativado!"); time.sleep(0.5); st.rerun()
                        
                        # --- LINHA FINA E COMPACTA AQUI (SUBSTITUIU ST.DIVIDER) ---
                        st.markdown('<hr style="margin: 2px 0; border: none; border-top: 1px solid #2b2b2b;">', unsafe_allow_html=True)
                else:
                    st.info("Nenhum aluno ativo encontrado.")

            with tab_n:
                turmas = db.executar_query("SELECT id, nome FROM turmas WHERE id_filial=%s", (id_filial,), fetch=True)
                opts_turma = {t['nome']: t['id'] for t in turmas} if turmas else {}
                
                st.subheader("Matricular Novo Aluno")
                c_data, c_aviso = st.columns([1, 2])
                nasc = c_data.date_input("Data de Nascimento", value=date(2015, 1, 1), min_value=date(1920, 1, 1), max_value=date.today())
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

                    if st.form_submit_button("Salvar"):
                        if not turma: st.error("Selecione turma.")
                        elif is_kid and not nm_resp: st.error("Responsável obrigatório.")
                        else:
                            ug = dt_ult if dt_ult else dt_inicio
                            res = db.executar_query(
                                """INSERT INTO usuarios (nome_completo, email, senha, telefone, data_nascimento, faixa, graus, id_filial, id_turma, perfil, status_conta, data_inicio, data_ultimo_grau, nome_responsavel, telefone_responsavel) 
                                VALUES (%s, %s, '123', %s, %s, %s, %s, %s, %s, 'aluno', 'Ativo', %s, %s, %s, %s)""",
                                (nome, email, zap, nasc, faixa, graus, id_filial, opts_turma[turma], dt_inicio, ug, nm_resp, tel_resp)
                            )
                            if res == "ERRO_DUPLICADO": st.error("Email já existe!")
                            elif res: st.success("Matriculado!"); st.rerun()