import streamlit as st
import database as db
import utils
import pandas as pd
import plotly.express as px
import time
from datetime import date
import views.admin as admin_view # Importamos o admin

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
    # CONTEXTO 1: GESTÃO DA REDE (CEO)
    # =======================================================
    if modo_visao == "🌍 Rede & Estratégia":
        # ... (TODA A PARTE DA REDE CONTINUA IGUAL A VERSÃO ANTERIOR) ...
        # ... (Vou omitir aqui para não ficar gigante, mas mantenha o código da Rede que já fizemos) ...
        # Se quiser que eu mande o código da Rede de novo, avisa. 
        # Mas o foco é a chamada abaixo:
        st.title("🌍 Painel Estratégico da Rede")
        
        tab_dash, tab_homolog, tab_filiais, tab_avisos = st.tabs([
            "📊 Dashboard Global", "🎓 Homologação Central", "🏢 Gestão de Filiais", "📢 Avisos Gerais"
        ])

        # 1. DASHBOARD GLOBAL
        with tab_dash:
            total_alunos = db.executar_query("SELECT COUNT(*) FROM usuarios WHERE status_conta='Ativo' AND perfil='aluno'", fetch=True)[0][0]
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

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🥋 Alunos na Rede", total_alunos)
            c2.metric("🏢 Filiais Ativas", total_filiais)
            label_pend = "✅ Homologação" if pendencias == 0 else "⚠️ Assinar Faixas"
            c3.metric(label_pend, pendencias)
            label_niver = "🎂 Niver Hoje" if qtd_niver == 0 else "🎉 Hoje é Festa!"
            c4.metric(label_niver, qtd_niver)

            st.divider()

            if qtd_niver > 0:
                st.info(f"🎈 **{qtd_niver} Aniversariante(s) hoje!** Mande os parabéns:")
                df_niver = pd.DataFrame(aniversariantes, columns=['Nome', 'Filial', 'WhatsApp'])
                st.dataframe(df_niver, use_container_width=True, hide_index=True)
            
            c_pizza, c_barras = st.columns([1, 1.5])
            with c_pizza:
                st.markdown("##### 🥋 Distribuição por Faixa")
                d_rede = db.executar_query("SELECT faixa, COUNT(*) as qtd FROM usuarios WHERE perfil='aluno' AND status_conta='Ativo' GROUP BY faixa", fetch=True)
                if d_rede: 
                    fig = px.pie(pd.DataFrame(d_rede, columns=['Faixa', 'Qtd']), values='Qtd', names='Faixa', hole=0.4, color='Faixa',
                                 color_discrete_map={'Branca': '#f0f0f0', 'Cinza': '#a0a0a0', 'Amarela': '#ffe135', 'Laranja': '#ff8c00', 'Verde': '#228b22', 'Azul': '#0000ff', 'Roxa': '#800080', 'Marrom': '#8b4513', 'Preta': '#000000'})
                    st.plotly_chart(fig, use_container_width=True)
            with c_barras:
                st.markdown("##### 📈 Top Filiais (Alunos)")
                d_fil = db.executar_query("SELECT f.nome, COUNT(u.id) as qtd FROM filiais f LEFT JOIN usuarios u ON f.id = u.id_filial AND u.status_conta='Ativo' GROUP BY f.nome ORDER BY qtd DESC", fetch=True)
                if d_fil: 
                    fig_bar = px.bar(pd.DataFrame(d_fil, columns=['Filial', 'Alunos']), x='Filial', y='Alunos', text='Alunos')
                    fig_bar.update_traces(textposition='outside')
                    st.plotly_chart(fig_bar, use_container_width=True)

        # 2. HOMOLOGAÇÃO
        with tab_homolog:
            st.markdown("#### Assinatura de Faixas (Rede)")
            pendentes = db.executar_query("""
                SELECT s.id, u.nome_completo, f.nome as filial, s.faixa_atual, s.nova_faixa 
                FROM solicitacoes_graduacao s 
                JOIN usuarios u ON s.id_aluno=u.id 
                JOIN filiais f ON s.id_filial=f.id 
                WHERE s.status='Aguardando Homologacao'
            """, fetch=True)
            
            if pendentes:
                for p in pendentes:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 1])
                        c1.markdown(f"**{p['nome_completo']}**")
                        c1.caption(f"📍 {p['filial']}")
                        c2.markdown(f"{p['faixa_atual']} ➝ **{p['nova_faixa']}**")
                        if c3.button("✅ Assinar", key=f"hm_{p['id']}", use_container_width=True):
                            db.executar_query("UPDATE usuarios SET faixa=%s, graus=0, data_graduacao=CURRENT_DATE WHERE id=(SELECT id_aluno FROM solicitacoes_graduacao WHERE id=%s)", (p['nova_faixa'], p['id']))
                            db.executar_query("UPDATE solicitacoes_graduacao SET status='Concluido' WHERE id=%s", (p['id'],))
                            st.toast("Homologado!"); time.sleep(1); st.rerun()
            else:
                st.success("Tudo em dia! Nenhuma graduação pendente de assinatura.")

        # 3. FILIAIS (COM CADASTRO E EDIÇÃO OTIMIZADOS)
        with tab_filiais:
            if 'form_filial' not in st.session_state: 
                st.session_state.form_filial = {"rua": "", "bairro": "", "cidade": "", "uf": ""}
            if 'editando_filial_id' not in st.session_state:
                st.session_state.editando_filial_id = None

            if st.session_state.editando_filial_id:
                dados = db.executar_query("SELECT * FROM filiais WHERE id=%s", (st.session_state.editando_filial_id,), fetch=True)[0]
                val_nome = dados['nome']
                val_tel = dados['telefone_contato']
                val_cep = dados['cep']
                partes_end = dados['endereco'].split(',') if dados['endereco'] else [""]
                val_rua = partes_end[0].strip()
                val_comp = partes_end[1].strip() if len(partes_end) > 1 else ""
                val_num = dados['numero']
                val_bairro = dados['bairro']
                val_cid = dados['cidade']
                val_uf = dados['estado']
                
                st.session_state.form_filial['rua'] = val_rua
                st.session_state.form_filial['bairro'] = val_bairro
                st.session_state.form_filial['cidade'] = val_cid
                st.session_state.form_filial['uf'] = val_uf
                
                lbl_bt = "💾 Salvar Alterações"
                expandir_form = True 
            else:
                val_nome, val_tel, val_cep, val_comp, val_num = "", "", "", "", ""
                val_rua = st.session_state.form_filial.get('rua', "")
                val_bairro = st.session_state.form_filial.get('bairro', "")
                val_cid = st.session_state.form_filial.get('cidade', "")
                val_uf = st.session_state.form_filial.get('uf', "")
                lbl_bt = "➕ Cadastrar Nova Filial"
                expandir_form = False

            with st.expander(f"{'✏️ Editando Filial' if st.session_state.editando_filial_id else '➕ Cadastrar Nova Filial'}", expanded=expandir_form):
                c_nf, c_resp, c_tf = st.columns([2, 2, 1]) 
                with c_nf: nf = st.text_input("Nome da Filial", value=val_nome)
                with c_resp:
                    users = db.executar_query("SELECT id, nome_completo FROM usuarios ORDER BY nome_completo", fetch=True)
                    d_u = {u['nome_completo']: u['id'] for u in users} if users else {}
                    resp = st.selectbox("Professor Responsável", list(d_u.keys())) if d_u else None
                with c_tf: tf = st.text_input("Telefone", value=val_tel)

                c_cep, c_rua, c_num, c_comp = st.columns([0.8, 2.5, 0.7, 1.2])
                with c_cep: cep = st.text_input("CEP", value=val_cep, key="cep_input_key", on_change=utils.buscar_dados_cep, max_chars=9)
                with c_rua: rua = st.text_input("Logradouro", value=val_rua) 
                with c_num: num = st.text_input("Nº", value=val_num)
                with c_comp: comp = st.text_input("Complemento", value=val_comp)

                c_bairro, c_cid, c_uf = st.columns([1.5, 1.5, 0.5])
                with c_bairro: bairro = st.text_input("Bairro", value=val_bairro)
                with c_cid: cidade = st.text_input("Cidade", value=val_cid)
                with c_uf: uf = st.text_input("UF", value=val_uf, max_chars=2)

                st.write("")
                bt1, bt2, bt3 = st.columns([1.5, 1, 4]) 
                
                if bt1.button(lbl_bt, type="primary", use_container_width=True):
                    if nf and resp:
                        end_final = f"{rua}, {comp}" if comp else rua
                        if st.session_state.editando_filial_id:
                            db.executar_query("UPDATE filiais SET nome=%s, responsavel_nome=%s, telefone_contato=%s, cep=%s, endereco=%s, numero=%s, bairro=%s, cidade=%s, estado=%s WHERE id=%s", 
                                            (nf, resp, tf, cep, end_final, num, bairro, cidade, uf, st.session_state.editando_filial_id))
                            st.success("Atualizado!"); st.session_state.editando_filial_id = None; time.sleep(1); st.rerun()
                        else:
                            db.executar_query("INSERT INTO filiais (nome, responsavel_nome, telefone_contato, cep, endereco, numero, bairro, cidade, estado) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", 
                                            (nf, resp, tf, cep, end_final, num, bairro, cidade, uf))
                            st.success("Cadastrado!"); time.sleep(1); st.rerun()
                    else: st.error("Preencha campos obrigatórios.")
                
                if bt2.button("🧹 Limpar", use_container_width=True):
                    st.session_state.editando_filial_id = None
                    st.session_state.form_filial = {"rua": "", "bairro": "", "cidade": "", "uf": ""}
                    st.rerun()

            st.divider()
            st.markdown("#### 🏢 Unidades da Rede")
            
            fs = db.executar_query("SELECT * FROM filiais ORDER BY nome", fetch=True)
            if fs:
                for f in fs:
                    col_txt, col_btn = st.columns([0.9, 0.1])
                    with col_txt:
                        q_alunos = db.executar_query("SELECT COUNT(*) FROM usuarios WHERE id_filial=%s AND status_conta='Ativo' AND perfil='aluno'", (f['id'],), fetch=True)[0][0]
                        turmas_f = db.executar_query("SELECT nome, dias, horario FROM turmas WHERE id_filial=%s", (f['id'],), fetch=True)
                        with st.expander(f"🏢 {f['nome']} ({f['cidade']}/{f['estado']})"):
                            c_info, c_stats = st.columns([1.5, 2])
                            with c_info:
                                st.markdown(f"**Resp:** {f['responsavel_nome']} | **Tel:** {f['telefone_contato']}")
                                st.caption(f"{f['endereco']}, {f['numero']} - {f['bairro']}")
                            with c_stats:
                                st.metric("Alunos", q_alunos)
                                if turmas_f:
                                    for t in turmas_f: st.code(f"{t['nome']} | {t['dias']} {t['horario']}", language="text")
                                else: st.caption("Sem turmas")
                    with col_btn:
                        b_ed, b_del = st.columns([1, 1], gap="small")
                        with b_ed:
                            if st.button("✏️", key=f"ed_{f['id']}", help="Editar Filial"):
                                st.session_state.editando_filial_id = f['id']
                                st.rerun()
                        with b_del:
                            if st.button("🗑️", key=f"del_{f['id']}", help="Excluir Filial"):
                                if q_alunos > 0: st.toast("❌ Impossível: Tem alunos!")
                                else:
                                    db.executar_query("DELETE FROM filiais WHERE id=%s", (f['id'],))
                                    st.toast("🗑️ Removido!"); time.sleep(1); st.rerun()

# 4. CENTRAL DE AVISOS (TOTALMENTE NOVA 🚀)
        with tab_avisos:
            st.markdown("### 📢 Central de Comunicação da Rede")
            
            # --- CONFIGURAÇÃO DE MODELOS (TEMPLATES) ---
            MODELOS = {
                "--- Selecione um modelo ---": "",
                "🎉 Aniversariantes": "Parabéns aos guerreiros que completam mais um ano de vida este mês! Que venham muitos anos de tatame e evolução. Oss! 🥋🎂",
                "💰 Mensalidade": "Lembrete: O vencimento da sua mensalidade está próximo. Mantenha seu cadastro em dia para continuar evoluindo. Oss!",
                "📅 Feriado": "Aviso: Não haverá treino nesta data devido ao feriado. Retornamos nossas atividades normais no dia X. Bom descanso!",
                "🏆 Graduação": "Atenção Equipe! Nossa cerimônia de graduação está marcada. Preparem seus kimonos e convidem seus familiares!",
                "🛑 Aviso Importante": "Comunicado urgente: [Escreva aqui seu aviso]"
            }

            # Estado para controlar o texto ao trocar o template
            if 'msg_atual' not in st.session_state: st.session_state.msg_atual = ""

            # Função callback para atualizar texto
            def atualizar_texto():
                escolha = st.session_state.sel_modelo
                if escolha != "--- Selecione um modelo ---":
                    st.session_state.msg_atual = MODELOS[escolha]

            # --- FORMULÁRIO DE ENVIO ---
            with st.container(border=True):
                c_mod, c_pub = st.columns([1, 1])
                
                # Seletor de Modelo
                c_mod.selectbox("📂 Carregar Modelo Rápido", list(MODELOS.keys()), key="sel_modelo", on_change=atualizar_texto)
                
                # Seletor de Público
                publico = c_pub.selectbox("🎯 Público Alvo", ["Todos", "Alunos", "Professores", "Admins Filiais"])
                
                st.markdown("---")
                
                # Campos de Texto
                titulo = st.text_input("Título do Aviso (Ex: Feriado de Carnaval)")
                # O text_area pega o valor do session_state
                mensagem = st.text_area("Mensagem", value=st.session_state.msg_atual, height=150)
                
                c_btn, c_info = st.columns([1, 3])
                if c_btn.button("🚀 Enviar Comunicado", type="primary", use_container_width=True):
                    if titulo and mensagem:
                        db.executar_query(
                            "INSERT INTO avisos (titulo, mensagem, publico_alvo, data_postagem, ativo) VALUES (%s, %s, %s, CURRENT_DATE, TRUE)",
                            (titulo, mensagem, publico)
                        )
                        st.success("Aviso publicado com sucesso!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Preencha o título e a mensagem.")
                
                c_info.caption(f"Este aviso será visível para: **{publico}**")

            # --- HISTÓRICO DE AVISOS ---
            st.divider()
            st.markdown("#### 📜 Histórico de Envios")
            
            # Busca avisos (ordenados do mais novo pro mais antigo)
            historico = db.executar_query("SELECT id, data_postagem, titulo, publico_alvo, ativo FROM avisos ORDER BY id DESC", fetch=True)
            
            if historico:
                # Cabeçalho da Tabela Visual
                col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([1, 2, 1.5, 1, 1])
                col_h1.markdown("**Data**")
                col_h2.markdown("**Título**")
                col_h3.markdown("**Público**")
                col_h4.markdown("**Status**")
                col_h5.markdown("**Ação**")
                
                for av in historico:
                    c1, c2, c3, c4, c5 = st.columns([1, 2, 1.5, 1, 1])
                    c1.write(av['data_postagem'].strftime('%d/%m'))
                    c2.write(av['titulo'])
                    
                    # Badge visual para o público
                    cor_badge = "blue" if av['publico_alvo'] == 'Todos' else "orange"
                    c3.markdown(f":{cor_badge}[{av['publico_alvo']}]")
                    
                    # Status
                    status_icon = "🟢 Ativo" if av['ativo'] else "🔴 Inativo"
                    c4.write(status_icon)
                    
                    # Botão de Excluir/Desativar
                    if c5.button("🗑️", key=f"del_av_{av['id']}", help="Apagar Aviso"):
                        db.executar_query("DELETE FROM avisos WHERE id=%s", (av['id'],))
                        st.toast("Aviso removido!")
                        time.sleep(0.5)
                        st.rerun()
                    
                    st.divider() # Linha separadora fina
            else:
                st.info("Nenhum comunicado enviado ainda.")

    # =======================================================
    # CONTEXTO 2: REUTILIZANDO O CÓDIGO DO ADMIN! 🚀
    # =======================================================
    elif modo_visao == "🥋 Minha Sede (Aulas)":
        # Chamamos a função do admin, mas pedimos para NÃO desenhar a sidebar (False)
        # Assim o Leader mantém a sidebar dele e o conteúdo é 100% igual ao do Adm.
        admin_view.painel_adm_filial(renderizar_sidebar=False)