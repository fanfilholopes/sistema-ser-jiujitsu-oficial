import streamlit as st
import database as db
import utils
import pandas as pd
import plotly.express as px
import time
from datetime import date

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

        # 3. FILIAIS (CORRIGIDO E OTIMIZADO 📍)
        with tab_filiais:
            # Inicializa estados
            if 'form_filial' not in st.session_state: 
                st.session_state.form_filial = {"rua": "", "bairro": "", "cidade": "", "uf": ""}
            if 'editando_filial_id' not in st.session_state:
                st.session_state.editando_filial_id = None

            # --- PREPARAÇÃO DOS DADOS (RESOLVE O BUG DO CACHE) ---
            if st.session_state.editando_filial_id:
                # MODO EDIÇÃO: Força dados do banco
                dados = db.executar_query("SELECT * FROM filiais WHERE id=%s", (st.session_state.editando_filial_id,), fetch=True)[0]
                
                val_nome = dados['nome']
                val_tel = dados['telefone_contato']
                val_cep = dados['cep']
                # Separa Rua e Complemento (Gambiarra inteligente para não mudar o banco)
                partes_end = dados['endereco'].split(',') if dados['endereco'] else [""]
                val_rua = partes_end[0].strip()
                val_comp = partes_end[1].strip() if len(partes_end) > 1 else ""
                
                val_num = dados['numero']
                val_bairro = dados['bairro']
                val_cid = dados['cidade']
                val_uf = dados['estado']
                
                # Sincroniza sessão para não bugar o utils.buscar_cep
                st.session_state.form_filial['rua'] = val_rua
                st.session_state.form_filial['bairro'] = val_bairro
                st.session_state.form_filial['cidade'] = val_cid
                st.session_state.form_filial['uf'] = val_uf
                
                lbl_bt = "💾 Salvar Alterações"
                expandir_form = True # Abre o form automaticamente
            else:
                # MODO NOVO: Usa sessão (para CEP funcionar) ou vazio
                val_nome, val_tel, val_cep, val_comp, val_num = "", "", "", "", ""
                # Lê do cache do CEP ou vazio
                val_rua = st.session_state.form_filial.get('rua', "")
                val_bairro = st.session_state.form_filial.get('bairro', "")
                val_cid = st.session_state.form_filial.get('cidade', "")
                val_uf = st.session_state.form_filial.get('uf', "")
                
                lbl_bt = "➕ Cadastrar Nova Filial"
                expandir_form = False

            # --- FORMULÁRIO ---
            with st.expander(f"{'✏️ Editando Filial' if st.session_state.editando_filial_id else '➕ Cadastrar Nova Filial'}", expanded=expandir_form):
                # LINHA 1: IDENTIDADE (3 Colunas)
                c_nf, c_resp, c_tf = st.columns([2, 2, 1]) 
                with c_nf: nf = st.text_input("Nome da Filial", value=val_nome)
                with c_resp:
                    users = db.executar_query("SELECT id, nome_completo FROM usuarios ORDER BY nome_completo", fetch=True)
                    d_u = {u['nome_completo']: u['id'] for u in users} if users else {}
                    resp = st.selectbox("Professor Responsável", list(d_u.keys())) if d_u else None
                with c_tf: tf = st.text_input("Telefone", value=val_tel)

                # LINHA 2: ENDEREÇO A (4 Colunas)
                c_cep, c_rua, c_num, c_comp = st.columns([0.8, 2.5, 0.7, 1.2])
                with c_cep: cep = st.text_input("CEP", value=val_cep, key="cep_input_key", on_change=utils.buscar_dados_cep, max_chars=9)
                with c_rua: rua = st.text_input("Logradouro", value=val_rua) # Lê da variavel tratada acima
                with c_num: num = st.text_input("Nº", value=val_num)
                with c_comp: comp = st.text_input("Complemento", value=val_comp)

                # LINHA 3: ENDEREÇO B (3 Colunas)
                c_bairro, c_cid, c_uf = st.columns([1.5, 1.5, 0.5])
                with c_bairro: bairro = st.text_input("Bairro", value=val_bairro)
                with c_cid: cidade = st.text_input("Cidade", value=val_cid)
                with c_uf: uf = st.text_input("UF", value=val_uf, max_chars=2)

                st.write("")
                # BOTÕES DE AÇÃO DO FORM
                bt1, bt2, bt3 = st.columns([1.5, 1, 4]) # Botões a esquerda
                
                # Botão Salvar
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
                
                # Botão Limpar
                if bt2.button("🧹 Limpar", use_container_width=True):
                    st.session_state.editando_filial_id = None
                    st.session_state.form_filial = {"rua": "", "bairro": "", "cidade": "", "uf": ""}
                    st.rerun()

            st.divider()
            st.markdown("#### 🏢 Unidades da Rede")
            
            # --- LISTA INTELIGENTE (BOTÕES COLADOS) ---
            fs = db.executar_query("SELECT * FROM filiais ORDER BY nome", fetch=True)
            if fs:
                for f in fs:
                    # Layout: 90% Texto | 10% Botões
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
                        # Colunas aninhadas para aproximar os botões ao máximo
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

        # 4. AVISOS
        with tab_avisos:
            st.markdown("#### Mural de Avisos")
            with st.form("msg_lid"):
                msg = st.text_area("Aviso Global")
                if st.form_submit_button("Publicar"):
                    db.executar_query("UPDATE avisos SET ativo=FALSE")
                    db.executar_query("INSERT INTO avisos (mensagem, ativo) VALUES (%s, TRUE)", (msg,))
                    st.success("Enviado!"); st.rerun()

    # =======================================================
    # CONTEXTO 2: OPERACIONAL (PROFESSOR DA SEDE)
    # =======================================================
    elif modo_visao == "🥋 Minha Sede (Aulas)":
        st.title("🥋 Gestão da Sede")
        
        nome_sede = db.executar_query("SELECT nome FROM filiais WHERE id=%s", (id_filial_sede,), fetch=True)
        st.caption(f"Unidade: {nome_sede[0]['nome'] if nome_sede else 'Sede'}")

        tab_chamada, tab_alunos, tab_grad_sede, tab_turmas = st.tabs([
            "✅ Chamada", "👥 Meus Alunos", "🎓 Graduar", "📅 Turmas"
        ])

        # 1. CHAMADA
        with tab_chamada:
            turmas = db.executar_query("SELECT id, nome FROM turmas WHERE id_filial=%s", (id_filial_sede,), fetch=True)
            d_t = {t['nome']: t['id'] for t in turmas} if turmas else {}
            st_t = st.selectbox("Turma", list(d_t.keys()), key="lid_t") if d_t else None
            
            if st_t:
                id_t = d_t[st_t]
                ja_veio = [x[0] for x in db.executar_query("SELECT id_aluno FROM checkins WHERE id_turma=%s AND data_aula=CURRENT_DATE", (id_t,), fetch=True)]
                als = db.executar_query("SELECT id, nome_completo, faixa FROM usuarios WHERE id_turma=%s AND status_conta='Ativo' ORDER BY nome_completo", (id_t,), fetch=True)
                
                with st.form("ch_lid"):
                    st.write(f"**Data:** {date.today().strftime('%d/%m/%Y')}")
                    checks = []
                    col_form = st.columns(2)
                    for i, a in enumerate(als):
                        with col_form[i % 2]:
                            is_checked = a['id'] in ja_veio
                            if st.checkbox(f"{a['nome_completo']} ({a['faixa']})", value=is_checked, key=f"cl_{a['id']}"): 
                                checks.append(a['id'])
                    
                    st.write("")
                    if st.form_submit_button("💾 Salvar"):
                        db.executar_query("DELETE FROM checkins WHERE id_turma=%s AND data_aula=CURRENT_DATE", (id_t,))
                        for uid in checks: db.executar_query("INSERT INTO checkins (id_aluno, id_turma, id_filial, data_aula) VALUES (%s, %s, %s, CURRENT_DATE)", (uid, id_t, id_filial_sede))
                        st.success("Salvo!"); time.sleep(0.5); st.rerun()

        # 2. ALUNOS
        with tab_alunos:
            sub_lista, sub_novo = st.tabs(["Lista", "Matricular"])
            
            with sub_lista:
                df = pd.DataFrame(db.executar_query("SELECT nome_completo as Nome, faixa as Faixa, telefone as Tel FROM usuarios WHERE id_filial=%s AND perfil='aluno' AND status_conta='Ativo'", (id_filial_sede,), fetch=True), columns=['Nome', 'Faixa', 'Tel'])
                st.dataframe(df, use_container_width=True, hide_index=True)

            with sub_novo:
                st.markdown("#### Matricular na Sede")
                turmas_sede = db.executar_query("SELECT id, nome FROM turmas WHERE id_filial=%s", (id_filial_sede,), fetch=True)
                opts_turma = {t['nome']: t['id'] for t in turmas_sede} if turmas_sede else {}
                
                c_data, c_aviso = st.columns([1, 2])
                nasc = c_data.date_input("Nascimento", value=date(2015, 1, 1), key="nlid")
                idade = (date.today() - nasc).days // 365
                is_kid = idade < 16
                
                if is_kid: c_aviso.warning(f"👶 KIDS ({idade} anos)")
                else: c_aviso.success(f"🥋 ADULTO ({idade} anos)")

                with st.form("form_aluno_lid"):
                    c1, c2 = st.columns([2, 1])
                    nome = c1.text_input("Nome")
                    turma = c2.selectbox("Turma", list(opts_turma.keys())) if opts_turma else None
                    c3, c4 = st.columns(2)
                    faixa = c3.selectbox("Faixa", utils.ORDEM_FAIXAS)
                    graus = c4.selectbox("Graus", [0,1,2,3,4])
                    c5, c6 = st.columns(2)
                    dt_inicio = c5.date_input("Início", date.today())
                    dt_ult = c6.date_input("Último Grau", value=None)
                    c7, c8 = st.columns(2)
                    zap = c7.text_input("WhatsApp")
                    email = c8.text_input("E-mail")
                    
                    nm_resp, tel_resp = None, None
                    if is_kid:
                        st.markdown("**Responsável:**")
                        c_r1, c_r2 = st.columns(2)
                        nm_resp = c_r1.text_input("Nome Resp.")
                        tel_resp = c_r2.text_input("Tel Resp.")

                    if st.form_submit_button("Matricular"):
                        if not turma: st.error("Escolha a turma.")
                        else:
                            ug = dt_ult if dt_ult else dt_inicio
                            try:
                                db.executar_query(
                                    """INSERT INTO usuarios (nome_completo, email, senha, telefone, data_nascimento, faixa, graus, id_filial, id_turma, perfil, status_conta, data_inicio, data_ultimo_grau, nome_responsavel, telefone_responsavel) 
                                    VALUES (%s, %s, '123', %s, %s, %s, %s, %s, %s, 'aluno', 'Ativo', %s, %s, %s, %s)""",
                                    (nome, email, zap, nasc, faixa, graus, id_filial_sede, opts_turma[turma], dt_inicio, ug, nm_resp, tel_resp)
                                )
                                st.success("Matriculado!"); time.sleep(1); st.rerun()
                            except: st.error("Email já existe.")

        # 3. GRADUAÇÃO
        with tab_grad_sede:
            my_alunos = db.executar_query("SELECT id, nome_completo, faixa, graus FROM usuarios WHERE id_filial=%s AND perfil='aluno' AND status_conta='Ativo' ORDER BY nome_completo", (id_filial_sede,), fetch=True)
            if my_alunos:
                for a in my_alunos:
                    with st.expander(f"{a['nome_completo']} ({a['faixa']} {a['graus']}º)"):
                        c1, c2 = st.columns(2)
                        if c1.button("+1 Grau", key=f"g_l_{a['id']}"):
                            db.executar_query("UPDATE usuarios SET graus = graus + 1, data_ultimo_grau = CURRENT_DATE WHERE id=%s", (a['id'],))
                            st.toast("Grau +1"); time.sleep(1); st.rerun()
                        nf = utils.get_proxima_faixa(a['faixa'])
                        if c2.button(f"Indicar {nf}", key=f"ind_l_{a['id']}"):
                            db.executar_query("INSERT INTO solicitacoes_graduacao (id_aluno, id_filial, faixa_atual, nova_faixa, status) VALUES (%s, %s, %s, %s, 'Aguardando Homologacao')", (a['id'], id_filial_sede, a['faixa'], nf))
                            st.success("Indicado!"); time.sleep(1); st.rerun()

        # 4. TURMAS
        with tab_turmas:
            c1, c2 = st.columns([1, 2])
            with c1:
                with st.form("nt_lid"):
                    tn = st.text_input("Nome")
                    td = st.text_input("Dias")
                    th = st.text_input("Horário")
                    if st.form_submit_button("Criar"):
                        db.executar_query("INSERT INTO turmas (nome, dias, horario, responsavel, id_filial) VALUES (%s, %s, %s, 'Mestre', %s)", (tn, td, th, id_filial_sede))
                        st.rerun()
            with c2:
                ts = db.executar_query("SELECT nome, dias, horario FROM turmas WHERE id_filial=%s", (id_filial_sede,), fetch=True)
                if ts: st.dataframe(pd.DataFrame(ts, columns=['Turma', 'Dias', 'Horário']), use_container_width=True, hide_index=True)