import streamlit as st
import database as db
import utils
import pandas as pd
import plotly.express as px
import time
from datetime import date
import views.admin as admin_view

def painel_lider():
    user = st.session_state.usuario
    id_filial_sede = user['id_filial']

    # --- SIDEBAR ---
    try: st.sidebar.image("logoser.jpg", width=150)
    except: pass
    
    st.sidebar.title("Painel Mestre 👑")
    st.sidebar.caption(f"Olá, {user['nome_completo']}")
    st.sidebar.markdown("---")
    
    st.sidebar.markdown("### 🔭 Modo de Visão")
    modo_visao = st.sidebar.radio(
        "Contexto:",
        ["🌍 Rede & Estratégia", "🥋 Minha Sede (Aulas)"],
        label_visibility="collapsed"
    )
    
    st.sidebar.markdown("---")
    c1, c2 = st.sidebar.columns(2)
    if c1.button("Sair"): st.session_state.logado = False; st.rerun()
    if c2.button("⏪"): st.session_state.sidebar_state = 'collapsed'; st.rerun()

    # =======================================================
    # CONTEXTO 1: GESTÃO DA REDE (CEO / ESTRATÉGICO)
    # =======================================================
    if modo_visao == "🌍 Rede & Estratégia":
        st.title("🌍 Painel Estratégico da Rede")
        
        tab_dash, tab_alunos_global, tab_homolog, tab_filiais, tab_avisos = st.tabs([
            "📊 Dashboard", "👥 Alunos Global", "🎓 Homologação", "🏢 Gestão de Filiais", "📢 Avisos"
        ])

        # 1. DASHBOARD GLOBAL
        with tab_dash:
            # Consultas de Totais
            total_alunos = db.executar_query("SELECT COUNT(*) FROM usuarios WHERE status_conta='Ativo' AND perfil='aluno'", fetch=True)[0][0]
            total_inativos = db.executar_query("SELECT COUNT(*) FROM usuarios WHERE status_conta='Inativo' AND perfil='aluno'", fetch=True)[0][0]
            total_profs = db.executar_query("SELECT COUNT(*) FROM usuarios WHERE status_conta='Ativo' AND perfil IN ('professor', 'lider', 'monitor')", fetch=True)[0][0]
            total_filiais = db.executar_query("SELECT COUNT(*) FROM filiais", fetch=True)[0][0]
            pendencias = db.executar_query("SELECT COUNT(*) FROM solicitacoes_graduacao WHERE status='Aguardando Homologacao'", fetch=True)[0][0]
            
            q_niver = """
                SELECT u.nome_completo, f.nome as filial, u.telefone 
                FROM usuarios u 
                JOIN filiais f ON u.id_filial = f.id
                WHERE u.status_conta='Ativo' 
                AND EXTRACT(MONTH FROM u.data_nascimento) = EXTRACT(MONTH FROM CURRENT_DATE)
                AND EXTRACT(DAY FROM u.data_nascimento) = EXTRACT(DAY FROM CURRENT_DATE)
            """
            aniversariantes = db.executar_query(q_niver, fetch=True)
            qtd_niver = len(aniversariantes) if aniversariantes else 0

            # --- KPIs ---
            k1, k2, k3, k4, k5, k6 = st.columns(6)
            k1.metric("Alunos Ativos", total_alunos)
            k2.metric("🚫 Inativos", total_inativos)
            k3.metric("🥋 Professores", total_profs)
            k4.metric("🏢 Filiais", total_filiais)
            
            label_pend = "✅ Em dia" if pendencias == 0 else "⚠️ Assinar"
            k5.metric("Homologação", pendencias, delta=label_pend, delta_color="inverse" if pendencias > 0 else "normal")
            
            label_niver = "🎂 Niver" if qtd_niver == 0 else "🎉 Festa!"
            k6.metric(label_niver, qtd_niver)

            st.divider()

            if qtd_niver > 0:
                with st.expander(f"🎈 Ver Aniversariantes ({qtd_niver})"):
                    st.dataframe(pd.DataFrame(aniversariantes, columns=['Nome', 'Filial', 'WhatsApp']), use_container_width=True, hide_index=True)
            
            # --- GRÁFICOS ESTATÍSTICOS ---
            c_pizza, c_barras = st.columns([1, 1.5])
            cores_map = {'Branca': '#f0f0f0', 'Cinza': '#a0a0a0', 'Amarela': '#ffe135', 'Laranja': '#ff8c00', 'Verde': '#228b22', 'Azul': '#0000ff', 'Roxa': '#800080', 'Marrom': '#8b4513', 'Preta': '#000000'}

            with c_pizza:
                st.markdown("##### 🥋 Por Faixa")
                d_rede = db.executar_query("SELECT faixa, COUNT(*) as qtd FROM usuarios WHERE perfil='aluno' AND status_conta='Ativo' GROUP BY faixa", fetch=True)
                if d_rede: 
                    fig = px.pie(pd.DataFrame(d_rede, columns=['Faixa', 'Qtd']), values='Qtd', names='Faixa', hole=0.4, color='Faixa', color_discrete_map=cores_map)
                    fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
                    st.plotly_chart(fig, use_container_width=True)
            
            with c_barras:
                st.markdown("##### 📈 Top Filiais (Qtd Alunos)")
                d_fil = db.executar_query("""
                    SELECT f.nome, COUNT(u.id) as qtd 
                    FROM filiais f 
                    LEFT JOIN usuarios u ON f.id = u.id_filial 
                    AND u.status_conta='Ativo' 
                    AND u.perfil='aluno' 
                    GROUP BY f.nome 
                    ORDER BY qtd DESC
                """, fetch=True)
                
                if d_fil: 
                    fig_bar = px.bar(pd.DataFrame(d_fil, columns=['Filial', 'Alunos']), x='Filial', y='Alunos', text='Alunos')
                    fig_bar.update_traces(textposition='outside')
                    st.plotly_chart(fig_bar, use_container_width=True)

            st.divider()

            # --- RANKINGS GLOBAIS (NOVO! 🏆) ---
            st.markdown("### 🏆 Destaques da Rede (Ano Atual)")
            c_rank_freq, c_rank_comp = st.columns(2)

            # 1. Casca Grossa Global (Frequência)
            with c_rank_freq:
                st.markdown("##### 🦍 Casca Grossa (Frequência)")
                sql_freq_global = """
                    SELECT u.nome_completo, f.nome as filial, COUNT(c.id) as treinos
                    FROM checkins c
                    JOIN usuarios u ON c.id_aluno = u.id
                    JOIN filiais f ON c.id_filial = f.id
                    WHERE c.validado=TRUE AND EXTRACT(YEAR FROM c.data_aula) = %s
                    GROUP BY u.nome_completo, f.nome
                    ORDER BY treinos DESC LIMIT 5
                """
                rank_freq = db.executar_query(sql_freq_global, (date.today().year,), fetch=True)
                if rank_freq:
                    df_freq = pd.DataFrame(rank_freq, columns=['Atleta', 'Filial', 'Treinos'])
                    df_freq.index += 1
                    st.dataframe(df_freq, use_container_width=True)
                else: st.info("Sem dados de frequência este ano.")

            # 2. Competidores Global (Medalhas)
            with c_rank_comp:
                st.markdown("##### ⚔️ Top Competidores (Pontos)")
                sql_comp_global = """
                    SELECT u.nome_completo, f.nome as filial, SUM(hc.pontos) as pontos
                    FROM historico_competicoes hc
                    JOIN usuarios u ON hc.id_aluno = u.id
                    JOIN filiais f ON hc.id_filial = f.id
                    WHERE hc.status='Aprovado' AND EXTRACT(YEAR FROM hc.data_competicao) = %s
                    GROUP BY u.nome_completo, f.nome
                    ORDER BY pontos DESC LIMIT 5
                """
                rank_comp = db.executar_query(sql_comp_global, (date.today().year,), fetch=True)
                if rank_comp:
                    df_comp = pd.DataFrame(rank_comp, columns=['Atleta', 'Filial', 'Pontos'])
                    df_comp.index += 1
                    st.dataframe(df_comp, use_container_width=True)
                else: st.info("Sem medalhas registradas este ano.")

        # 2. ALUNOS GLOBAL
        with tab_alunos_global:
            if 'lider_edit_aluno_id' not in st.session_state: st.session_state.lider_edit_aluno_id = None
            
            with st.expander("➕ Matricular Novo Aluno na Rede"):
                st.markdown("##### Dados Cadastrais")
                lista_filiais = db.executar_query("SELECT id, nome FROM filiais ORDER BY nome", fetch=True)
                opts_filial_reg = {f['nome']: f['id'] for f in lista_filiais} if lista_filiais else {}

                c_data, c_aviso = st.columns([1, 2])
                nasc_reg = c_data.date_input("Data de Nascimento", value=date(2015, 1, 1), min_value=date(1920, 1, 1), max_value=date.today())
                idade = (date.today() - nasc_reg).days // 365
                is_kid = idade < 16
                if is_kid: c_aviso.warning(f"👶 KIDS ({idade} anos) - Dados do Responsável Obrigatórios.")
                else: c_aviso.success(f"🥋 ADULTO ({idade} anos)")

                with st.form("form_novo_aluno_rede"):
                    c1, c2 = st.columns([2, 1])
                    novo_nome_reg = c1.text_input("Nome Completo")
                    sel_filial_reg = c2.selectbox("Filial de Matrícula", list(opts_filial_reg.keys())) if opts_filial_reg else None
                    c3, c4, c5, c_ug = st.columns(4)
                    faixa_reg = c3.selectbox("Faixa Inicial", utils.ORDEM_FAIXAS)
                    grau_reg = c4.selectbox("Grau", [0,1,2,3,4])
                    dt_inicio_reg = c5.date_input("Data de Início", date.today())
                    dt_ult_grau_reg = c_ug.date_input("Data Último Grau", value=None)
                    c6, c7 = st.columns(2)
                    novo_zap_reg = c6.text_input("WhatsApp")
                    novo_email_reg = c7.text_input("E-mail (Será o Login)")
                    nm_resp, tel_resp = None, None
                    if is_kid:
                        st.divider(); st.markdown("###### 👨‍👩‍👧 Dados do Responsável")
                        c_r1, c_r2 = st.columns(2)
                        nm_resp = c_r1.text_input("Nome do Responsável")
                        tel_resp = c_r2.text_input("WhatsApp do Responsável")

                    st.write("")
                    if st.form_submit_button("💾 Realizar Matrícula", type="primary", use_container_width=True):
                        if not novo_nome_reg or not novo_email_reg or not sel_filial_reg:
                            st.error("Preencha os campos obrigatórios.")
                        elif is_kid and not nm_resp:
                            st.error("Dados do responsável obrigatórios.")
                        else:
                            id_filial_sel = opts_filial_reg[sel_filial_reg]
                            data_grad_final = dt_ult_grau_reg if dt_ult_grau_reg else dt_inicio_reg
                            res = db.executar_query(
                                """INSERT INTO usuarios (nome_completo, email, senha, telefone, data_nascimento, faixa, graus, id_filial, perfil, status_conta, data_inicio, data_ultimo_grau, nome_responsavel, telefone_responsavel) 
                                VALUES (%s, %s, '123', %s, %s, %s, %s, %s, 'aluno', 'Ativo', %s, %s, %s, %s)""",
                                (novo_nome_reg, novo_email_reg, novo_zap_reg, nasc_reg, faixa_reg, grau_reg, id_filial_sel, dt_inicio_reg, data_grad_final, nm_resp, tel_resp)
                            )
                            if res == "ERRO_DUPLICADO": st.error("E-mail já cadastrado!")
                            elif res: st.success("Matriculado com sucesso!"); time.sleep(1.5); st.rerun()

            st.markdown("---")

            if st.session_state.lider_edit_aluno_id:
                st.info("✏️ Editando Aluno")
                aluno_dados = db.executar_query("SELECT * FROM usuarios WHERE id=%s", (st.session_state.lider_edit_aluno_id,), fetch=True)[0]
                with st.container(border=True):
                    with st.form("form_edit_global"):
                        c_n, c_f = st.columns([2, 1])
                        novo_nome = c_n.text_input("Nome", value=aluno_dados['nome_completo'])
                        filial_atual_nome = next((k for k, v in opts_filial_reg.items() if v == aluno_dados['id_filial']), None)
                        nova_filial = c_f.selectbox("Transferir Filial", list(opts_filial_reg.keys()), index=list(opts_filial_reg.keys()).index(filial_atual_nome) if filial_atual_nome else 0)
                        c_faixa, c_grau = st.columns(2)
                        nova_faixa = c_faixa.selectbox("Faixa", utils.ORDEM_FAIXAS, index=utils.ORDEM_FAIXAS.index(aluno_dados['faixa']))
                        novo_grau = c_grau.selectbox("Grau", [0,1,2,3,4], index=aluno_dados['graus'])
                        c_b1, c_b2 = st.columns(2)
                        if c_b1.form_submit_button("💾 Salvar"):
                            db.executar_query("UPDATE usuarios SET nome_completo=%s, id_filial=%s, faixa=%s, graus=%s WHERE id=%s", 
                                              (novo_nome, opts_filial_reg[nova_filial], nova_faixa, novo_grau, st.session_state.lider_edit_aluno_id))
                            st.success("Salvo!"); st.session_state.lider_edit_aluno_id = None; time.sleep(0.5); st.rerun()
                        if c_b2.form_submit_button("Cancelar"):
                            st.session_state.lider_edit_aluno_id = None; st.rerun()
            else:
                c_top1, c_top2 = st.columns([3, 1])
                filtro_nome = c_top1.text_input("🔎 Buscar", placeholder="Nome...")
                opts_filial_filtro = {"Todas": None}
                opts_filial_filtro.update(opts_filial_reg)
                filtro_filial_nome = c_top2.selectbox("Filtrar", list(opts_filial_filtro.keys()))
                id_filial_filtro = opts_filial_filtro[filtro_filial_nome]

                query_base = """
                    SELECT u.id, u.nome_completo, u.faixa, f.nome as nome_filial 
                    FROM usuarios u 
                    LEFT JOIN filiais f ON u.id_filial = f.id 
                    WHERE u.perfil='aluno' AND u.status_conta='Ativo'
                """
                params = []
                if filtro_nome:
                    query_base += " AND u.nome_completo ILIKE %s"
                    params.append(f"%{filtro_nome}%")
                if id_filial_filtro:
                    query_base += " AND u.id_filial = %s"
                    params.append(id_filial_filtro)
                
                query_base += " ORDER BY u.nome_completo LIMIT 50"
                alunos_global = db.executar_query(query_base, tuple(params), fetch=True)

                st.markdown("### 📋 Relação de Alunos")
                if alunos_global:
                    for a in alunos_global:
                        c_info, c_btns = st.columns([4, 1.2])
                        c_info.markdown(f"**{a['nome_completo']}** <span style='color:grey; font-size:0.9em'>| {a['faixa']} | 🏢 {a['nome_filial']}</span>", unsafe_allow_html=True)
                        with c_btns:
                            b_ed, b_del = st.columns([1, 1], gap="small")
                            if b_ed.button("✏️", key=f"ged_{a['id']}"):
                                st.session_state.lider_edit_aluno_id = a['id']; st.rerun()
                            if b_del.button("🗑️", key=f"gdel_{a['id']}"):
                                db.executar_query("UPDATE usuarios SET status_conta='Inativo' WHERE id=%s", (a['id'],))
                                st.toast("Inativado!"); time.sleep(0.5); st.rerun()
                        st.markdown('<hr style="margin: 0px 0; border: none; border-top: 1px solid #2b2b2b;">', unsafe_allow_html=True)
                else: st.info("Nenhum aluno encontrado.")

        # 3. HOMOLOGAÇÃO
        with tab_homolog:
            st.markdown("#### Assinatura de Faixas")
            pendentes = db.executar_query("""
                SELECT s.id, u.nome_completo, f.nome as filial, s.faixa_atual, s.nova_faixa, s.id_aluno 
                FROM solicitacoes_graduacao s 
                JOIN usuarios u ON s.id_aluno=u.id 
                JOIN filiais f ON s.id_filial=f.id 
                WHERE s.status='Aguardando Homologacao'
            """, fetch=True)
            if pendentes:
                for p in pendentes:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 1])
                        c1.markdown(f"**{p['nome_completo']}** ({p['filial']})")
                        c2.markdown(f"{p['faixa_atual']} ➝ **{p['nova_faixa']}**")
                        if c3.button("✅ Assinar", key=f"hm_{p['id']}", use_container_width=True):
                            db.executar_query("UPDATE usuarios SET faixa=%s, graus=0, data_ultimo_grau=CURRENT_DATE WHERE id=%s", (p['nova_faixa'], p['id_aluno']))
                            db.executar_query("UPDATE solicitacoes_graduacao SET status='Concluido', data_conclusao=CURRENT_DATE WHERE id=%s", (p['id'],))
                            st.toast("Homologado!"); time.sleep(1); st.rerun()
            else: st.success("Tudo em dia!")

        # 4. GESTÃO DE FILIAIS (COM SELETOR DE RESPONSÁVEL E ADMINS INTEGRADOS)
        with tab_filiais:
            with st.container(border=True):
                st.markdown("#### ➕ Criar Nova Filial")
                with st.form("nova_filial_simples"):
                    c1, c2 = st.columns([3, 1])
                    nome_nova = c1.text_input("Nome da Filial")
                    if c2.form_submit_button("Criar Agora", type="primary", use_container_width=True):
                        if nome_nova:
                            db.executar_query("INSERT INTO filiais (nome) VALUES (%s)", (nome_nova,))
                            st.success("Filial criada!"); time.sleep(1); st.rerun()
                        else: st.error("Digite um nome.")

            st.divider()
            
            st.markdown("#### 🏢 Filiais Ativas")
            filiais = db.executar_query("SELECT * FROM filiais ORDER BY nome", fetch=True)
            
            if filiais:
                todos_usuarios = db.executar_query("SELECT id, nome_completo FROM usuarios WHERE status_conta='Ativo' ORDER BY nome_completo", fetch=True)
                lista_nomes_usuarios = [u['nome_completo'] for u in todos_usuarios] if todos_usuarios else []

                for f in filiais:
                    admins_da_filial = db.executar_query("SELECT id, nome_completo, email FROM usuarios WHERE id_filial=%s AND perfil='adm_filial' AND status_conta='Ativo'", (f['id'],), fetch=True)
                    
                    with st.expander(f"📍 {f['nome']} ({len(admins_da_filial)} Admins)"):
                        col_dados, col_admins = st.columns(2)
                        
                        with col_dados:
                            st.markdown("##### 📝 Dados")
                            idx_resp = 0
                            if f['responsavel_nome'] and f['responsavel_nome'] in lista_nomes_usuarios:
                                idx_resp = lista_nomes_usuarios.index(f['responsavel_nome'])
                            
                            with st.form(f"edit_filial_{f['id']}"):
                                novo_nome = st.text_input("Nome", value=f['nome'])
                                novo_resp = st.selectbox("Responsável", lista_nomes_usuarios, index=idx_resp) if lista_nomes_usuarios else st.text_input("Responsável", value=f['responsavel_nome'])
                                novo_tel = st.text_input("Telefone", value=f['telefone_contato'])
                                novo_end = st.text_area("Endereço", value=f['endereco'])
                                
                                if st.form_submit_button("💾 Salvar Dados"):
                                    db.executar_query("UPDATE filiais SET nome=%s, responsavel_nome=%s, telefone_contato=%s, endereco=%s WHERE id=%s", 
                                                      (novo_nome, novo_resp, novo_tel, novo_end, f['id']))
                                    st.toast("Atualizado!"); time.sleep(0.5); st.rerun()

                        with col_admins:
                            st.markdown("##### 👮 Admins")
                            if admins_da_filial:
                                for adm in admins_da_filial:
                                    c_a1, c_a2 = st.columns([3, 1])
                                    c_a1.write(f"👤 {adm['nome_completo']}")
                                    if c_a2.button("🗑️", key=f"rm_adm_{adm['id']}"):
                                        db.executar_query("UPDATE usuarios SET status_conta='Inativo' WHERE id=%s", (adm['id'],))
                                        st.rerun()
                            else: st.info("Sem admins.")

                            st.markdown("---")
                            with st.popover("➕ Novo Admin"):
                                st.write(f"Admin para **{f['nome']}**")
                                with st.form(f"new_adm_{f['id']}"):
                                    na_nome = st.text_input("Nome")
                                    na_email = st.text_input("Email")
                                    na_senha = st.text_input("Senha", type="password")
                                    if st.form_submit_button("Criar"):
                                        if na_nome and na_email and na_senha:
                                            res = db.executar_query("INSERT INTO usuarios (nome_completo, email, senha, id_filial, perfil, status_conta) VALUES (%s, %s, %s, %s, 'adm_filial', 'Ativo')", (na_nome, na_email, na_senha, f['id']))
                                            if res == "ERRO_DUPLICADO": st.error("Email em uso.")
                                            else: st.success("Criado!"); time.sleep(1); st.rerun()
                                        else: st.error("Preencha tudo.")

        # 5. AVISOS
        with tab_avisos:
            st.markdown("### 📢 Central de Comunicação")
            MODELOS = {
                "--- Selecione ---": "",
                "🎉 Aniversariantes": "Parabéns aos guerreiros que completam mais um ano de vida este mês! Oss! 🥋🎂",
                "💰 Mensalidade": "Lembrete: O vencimento da sua mensalidade está próximo. Oss!",
                "📅 Feriado": "Aviso: Não haverá treino nesta data devido ao feriado. Bom descanso!",
                "🏆 Graduação": "Atenção Equipe! Nossa cerimônia de graduação está marcada. Preparem seus kimonos!",
                "🛑 Importante": "Comunicado urgente: [Escreva aqui]"
            }
            if 'msg_atual' not in st.session_state: st.session_state.msg_atual = ""
            def atualizar_texto():
                escolha = st.session_state.sel_modelo
                if escolha != "--- Selecione ---": st.session_state.msg_atual = MODELOS[escolha]

            with st.container(border=True):
                c_mod, c_pub = st.columns([1, 1])
                c_mod.selectbox("📂 Modelo Rápido", list(MODELOS.keys()), key="sel_modelo", on_change=atualizar_texto)
                publico = c_pub.selectbox("🎯 Público", ["Todos", "Alunos", "Professores", "Admins Filiais"])
                titulo = st.text_input("Título")
                mensagem = st.text_area("Mensagem", value=st.session_state.msg_atual)
                if st.button("🚀 Enviar", type="primary", use_container_width=True):
                    if titulo and mensagem:
                        db.executar_query("INSERT INTO avisos (titulo, mensagem, publico_alvo, data_postagem, ativo) VALUES (%s, %s, %s, CURRENT_DATE, TRUE)", (titulo, mensagem, publico))
                        st.success("Enviado!"); time.sleep(1); st.rerun()
                    else: st.error("Preencha tudo.")

            st.divider()
            historico = db.executar_query("SELECT id, data_postagem, titulo, publico_alvo, ativo FROM avisos ORDER BY id DESC", fetch=True)
            if historico:
                col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([1, 2, 1.5, 1, 1])
                col_h1.markdown("**Data**"); col_h2.markdown("**Título**"); col_h3.markdown("**Público**"); col_h4.markdown("**Status**"); col_h5.markdown("**Ação**")
                for av in historico:
                    c1, c2, c3, c4, c5 = st.columns([1, 2, 1.5, 1, 1])
                    c1.write(av['data_postagem'].strftime('%d/%m'))
                    c2.write(av['titulo'])
                    cor_badge = "blue" if av['publico_alvo'] == 'Todos' else "orange"
                    c3.markdown(f":{cor_badge}[{av['publico_alvo']}]")
                    status_icon = "🟢" if av['ativo'] else "🔴"
                    c4.write(status_icon)
                    if c5.button("🗑️", key=f"del_av_{av['id']}"):
                        db.executar_query("DELETE FROM avisos WHERE id=%s", (av['id'],))
                        st.rerun()

    # =======================================================
    # CONTEXTO 2: VISÃO DE AULAS (SEDE)
    # =======================================================
    elif modo_visao == "🥋 Minha Sede (Aulas)":
        admin_view.painel_adm_filial(renderizar_sidebar=False)