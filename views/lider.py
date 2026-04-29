import streamlit as st
import database as db
import utils
import pandas as pd
import plotly.express as px
import time
import requests
from datetime import date
import views.admin as admin_view

def painel_lider():
    user = st.session_state.usuario
    perfil = user.get('perfil', 'lider')
    
    # =======================================================
    # 1. SIDEBAR DE COMANDO 👑
    # =======================================================
    try:
        st.sidebar.image("logoser.jpg", width=150)
    except:
        pass

    st.sidebar.title("Painel Mestre 👑")
    st.sidebar.markdown(f"Bem-vindo, **{user['nome_completo'].split(' ')[0]}**")
    
    st.sidebar.divider()
    
    st.sidebar.subheader("🔭 Modo de Visão")
    modo_visao = st.sidebar.radio(
        "Selecione o contexto:",
        ["🌍 Rede & Estratégia", "🥋 Minha Sede (Aulas)"],
        label_visibility="collapsed"
    )
    
    st.sidebar.divider()
    
    if st.sidebar.button("🚪 Sair do Sistema", use_container_width=True, type="secondary"):
        st.session_state.logado = False
        st.rerun()

    # =======================================================
    # CONTEXTO 1: ESTRATÉGICO (VISÃO GLOBAL DA REDE)
    # =======================================================
    if modo_visao == "🌍 Rede & Estratégia":
        st.title("🌍 Painel Estratégico")
        
        # Menu de Navegação Superior
        tab_dash, tab_alunos, tab_homolog, tab_filiais, tab_comunica = st.tabs([
            "📊 Dashboard", "👥 Alunos Global", "🎓 Homologação", "🏢 Filiais", "📢 Comunicados"
        ])

        # --- ABA 1: DASHBOARD GLOBAL ---
        with tab_dash:
            # Coleta de métricas
            total_ativos = db.executar_query("SELECT COUNT(*) FROM usuarios WHERE status_conta='Ativo' AND perfil IN ('aluno', 'monitor')", fetch=True)[0][0]
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

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Alunos Ativos", total_ativos)
            m2.metric("Unidades", total_filiais)
            m3.metric("Homologações", pendencias, delta="Pendentes" if pendencias > 0 else "Em dia", delta_color="inverse" if pendencias > 0 else "normal")
            m4.metric("Bolo de Hoje 🎂", f"{qtd_niver} atletas")

            if qtd_niver > 0:
                with st.expander("🎉 Ver Aniversariantes de Hoje"):
                    st.table(pd.DataFrame(aniversariantes, columns=['nome_completo', 'filial', 'telefone']))

            st.divider()

            g1, g2 = st.columns([1, 1.5])
            with g1:
                st.markdown("##### 🥋 Distribuição de Faixas")
                df_faixas_raw = db.executar_query("SELECT faixa, COUNT(*) as qtd FROM usuarios WHERE status_conta='Ativo' AND perfil IN ('aluno', 'monitor') GROUP BY faixa", fetch=True)
                if df_faixas_raw:
                    df_f = pd.DataFrame(df_faixas_raw, columns=['faixa', 'qtd'])
                    fig_f = px.pie(df_f, values='qtd', names='faixa', hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_f.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
                    st.plotly_chart(fig_f, use_container_width=True)

            with g2:
                st.markdown("##### 📈 Top Filiais (Alunos)")
                df_filiais_raw = db.executar_query("""
                    SELECT f.nome as filial, COUNT(u.id) as qtd
                    FROM filiais f 
                    LEFT JOIN usuarios u ON f.id = u.id_filial AND u.status_conta='Ativo' AND u.perfil IN ('aluno', 'monitor')
                    GROUP BY f.nome ORDER BY qtd DESC LIMIT 5
                """, fetch=True)
                if df_filiais_raw:
                    df_b = pd.DataFrame(df_filiais_raw, columns=['filial', 'qtd'])
                    fig_b = px.bar(df_b, x='filial', y='qtd', text='qtd', color='filial')
                    fig_b.update_layout(margin=dict(t=20, b=0, l=0, r=0), showlegend=False, xaxis_title=None, yaxis_title=None)
                    st.plotly_chart(fig_b, use_container_width=True)

        # --- ABA 2: ALUNOS GLOBAL ---
        with tab_alunos:
            st.subheader("👥 Gestão Global de Membros")
            with st.expander("➕ Matricular Novo Aluno na Rede"):
                with st.form("nova_matricula_global"):
                    c1, c2, c3 = st.columns([2,1,1])
                    n_nome = c1.text_input("Nome Completo")
                    n_email = c2.text_input("E-mail")
                    filiais_db = db.executar_query("SELECT id, nome FROM filiais ORDER BY nome", fetch=True)
                    d_filiais = {f['nome']: f['id'] for f in filiais_db} if filiais_db else {}
                    n_filial = c3.selectbox("Filial Destino", list(d_filiais.keys()))
                    
                    c4, c5, c6 = st.columns(3)
                    n_faixa = c4.selectbox("Faixa", utils.ORDEM_FAIXAS)
                    n_nasc = c5.date_input("Nascimento", value=date(2000,1,1), format="DD/MM/YYYY")
                    n_tel = c6.text_input("Telefone")
                    
                    if st.form_submit_button("Finalizar Matrícula", type="primary", use_container_width=True):
                        if n_nome and n_email and n_filial:
                            db.executar_query(
                                "INSERT INTO usuarios (nome_completo, email, senha, id_filial, faixa, data_nascimento, telefone, perfil, status_conta) VALUES (%s,%s,'123',%s,%s,%s,%s,'aluno','Ativo')",
                                (n_nome, n_email, d_filiais[n_filial], n_faixa, n_nasc, n_tel)
                            )
                            st.success(f"Aluno {n_nome} matriculado!")
                            time.sleep(1); st.rerun()

            st.divider()
            busca_g = st.text_input("🔍 Localizar aluno na rede...", placeholder="Digite o nome...")
            if busca_g:
                resultados = db.executar_query("""
                    SELECT u.id, u.nome_completo, u.faixa, f.nome as filial, u.status_conta
                    FROM usuarios u JOIN filiais f ON u.id_filial = f.id
                    WHERE u.nome_completo ILIKE %s ORDER BY u.nome_completo
                """, (f"%{busca_g}%",), fetch=True)
                if resultados:
                    for r in resultados:
                        with st.container(border=True):
                            col_r1, col_r2 = st.columns([4, 1])
                            col_r1.write(f"**{r['nome_completo']}** | {r['faixa']} | 📍 {r['filial']}")
                            if col_r2.button("Inativar", key=f"global_del_{r['id']}"):
                                db.executar_query("UPDATE usuarios SET status_conta='Inativo' WHERE id=%s", (r['id'],))
                                st.rerun()

        # --- ABA 3: HOMOLOGAÇÃO ---
        with tab_homolog:
            st.subheader("🎓 Homologação de Graduações")
            solicitacoes = db.executar_query("""
                SELECT s.id, u.nome_completo, f.nome as filial, s.faixa_atual, s.nova_faixa, s.id_aluno
                FROM solicitacoes_graduacao s
                JOIN usuarios u ON s.id_aluno = u.id
                JOIN filiais f ON s.id_filial = f.id
                WHERE s.status = 'Aguardando Homologacao'
            """, fetch=True)
            if solicitacoes:
                for s in solicitacoes:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 1])
                        c1.write(f"**{s['nome_completo']}** ({s['filial']})")
                        c2.info(f"{s['faixa_atual']} ➔ {s['nova_faixa']}")
                        if c3.button("✅ Homologar", key=f"hom_{s['id']}", use_container_width=True):
                            db.executar_query("UPDATE usuarios SET faixa=%s, graus=0 WHERE id=%s", (s['nova_faixa'], s['id_aluno']))
                            db.executar_query("UPDATE solicitacoes_graduacao SET status='Concluido' WHERE id=%s", (s['id'],))
                            st.success("Graduação assinada!"); time.sleep(0.5); st.rerun()
            else:
                st.success("Tudo em dia!")

        # --- ABA 4: GESTÃO DE FILIAIS (LAYOUT OTIMIZADO) ---
        with tab_filiais:
            st.subheader("🏢 Administração de Unidades")
            
            # 1. CADASTRO DE NOVA UNIDADE
            with st.expander("➕ Cadastrar Nova Unidade", expanded=False):
                with st.form("nova_filial_form_v3"):
                    # Linha 1: Dados Principais em 3 colunas
                    c1, c2, c3 = st.columns([2, 1, 1])
                    f_nome = c1.text_input("Nome da Unidade")
                    f_municipio = c2.text_input("Município")
                    f_estado = c3.text_input("UF", max_chars=2)
                    
                    # Linha 2: Contato e Logradouro
                    c4, c5 = st.columns([1, 2])
                    f_tel = c4.text_input("Telefone")
                    f_rua = c5.text_input("Logradouro (Rua, Nº, Bairro)")
                    
                    st.markdown("---")
                    st.caption("Escolha o usuário que será o Administrador desta unidade:")
                    
                    # Busca usuários ativos para promoção
                    u_lista = db.executar_query("SELECT id, nome_completo FROM usuarios WHERE status_conta='Ativo' ORDER BY nome_completo", fetch=True)
                    d_u = {u['nome_completo']: u['id'] for u in u_lista} if u_lista else {}
                    f_adm_nome = st.selectbox("Responsável / Admin", ["--- Selecione ---"] + list(d_u.keys()))
                    
                    if st.form_submit_button("🚀 Criar Unidade e Promover Admin", type="primary", use_container_width=True):
                        if f_nome and f_municipio and f_adm_nome != "--- Selecione ---":
                            loc_full = f"{f_rua} - {f_municipio}/{f_estado}"
                            
                            # Cria a filial
                            res = db.executar_query(
                                "INSERT INTO filiais (nome, endereco, telefone_contato, responsavel_nome) VALUES (%s, %s, %s, %s) RETURNING id",
                                (f_nome, loc_full, f_tel, f_adm_nome), fetch=True
                            )
                            
                            if res:
                                nova_id = res[0]['id']
                                id_user = d_u[f_adm_nome]
                                # Promove o usuário e vincula à filial
                                db.executar_query("UPDATE usuarios SET perfil='adm_filial', id_filial=%s WHERE id=%s", (nova_id, id_user))
                                st.success(f"Unidade '{f_nome}' criada com sucesso!")
                                time.sleep(1)
                                st.rerun()
                        else:
                            st.error("Preencha Nome, Município e selecione um Administrador.")

            st.divider()

            # 2. LISTAGEM COM EDIÇÃO E EXCLUSÃO (LAYOUT DE CARDS)
            st.markdown("#### 📍 Unidades Cadastradas")
            filiais_db = db.executar_query("SELECT * FROM filiais ORDER BY nome", fetch=True)
            
            if filiais_db:
                for f in filiais_db:
                    # Extrai Município/UF para o cabeçalho
                    cidade_uf = f['endereco'].split('-')[-1].strip() if '-' in f['endereco'] else ""
                    
                    with st.expander(f"📍 {f['nome']} | {cidade_uf}"):
                        with st.form(f"edit_f_{f['id']}"):
                            ce1, ce2, ce3 = st.columns([2, 1, 1])
                            u_nome = ce1.text_input("Nome da Unidade", value=f['nome'])
                            u_tel = ce2.text_input("Telefone", value=f['telefone_contato'])
                            u_resp = ce3.text_input("Admin Atual", value=f['responsavel_nome'], disabled=True)
                            
                            u_end = st.text_input("Endereço Completo", value=f['endereco'])
                            
                            # Botões de Ação
                            b_save, b_del, _ = st.columns([1, 1, 2])
                            
                            if b_save.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                                db.executar_query(
                                    "UPDATE filiais SET nome=%s, endereco=%s, telefone_contato=%s WHERE id=%s",
                                    (u_nome, u_end, u_tel, f['id'])
                                )
                                st.success("Atualizado!")
                                time.sleep(0.5)
                                st.rerun()
                                
                            if b_del.form_submit_button("🗑️ Excluir Unidade", use_container_width=True):
                                try:
                                    db.executar_query("DELETE FROM filiais WHERE id=%s", (f['id'],))
                                    st.warning("Unidade removida.")
                                    time.sleep(0.5)
                                    st.rerun()
                                except:
                                    st.error("Não é possível excluir: existem alunos vinculados a esta unidade.")
            else:
                st.info("Nenhuma filial cadastrada no sistema.")

        # --- ABA 5: COMUNICADOS ---
        with tab_comunica:
            st.subheader("📢 Mural de Avisos da Rede")
            with st.container(border=True):
                a_tit = st.text_input("Título do Aviso")
                a_msg = st.text_area("Mensagem")
                a_alvo = st.selectbox("Público Alvo", ["Todos", "Professores", "Alunos"])
                if st.button("Publicar Aviso na Rede", type="primary"):
                    db.executar_query("INSERT INTO avisos (titulo, mensagem, publico_alvo, data_postagem, ativo) VALUES (%s,%s,%s,CURRENT_DATE,TRUE)", (a_tit, a_msg, a_alvo))
                    st.success("Comunicado publicado!"); st.rerun()

    # =======================================================
    # CONTEXTO 2: OPERACIONAL (VISÃO DA SEDE)
    # =======================================================
    elif modo_visao == "🥋 Minha Sede (Aulas)":
        st.info(f"Operações da Sede: {user.get('nome_filial', 'Matriz')}")
        admin_view.painel_adm_filial(renderizar_sidebar=False)