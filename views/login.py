# views/login.py
import streamlit as st
import database as db
import utils
import time
from datetime import date

def mostrar_login():
    # --- LAYOUT: COLUNA CENTRAL LARGA PARA O CADASTRO ---
    col_esq, col_centro, col_dir = st.columns([0.2, 2, 0.2])

    with col_centro:
        # 1. LOGO E TÍTULO
        c_logo_esq, c_logo_centro, c_logo_dir = st.columns([1.5, 1, 1.5])
        with c_logo_centro:
            try: 
                st.image("logoser.jpg", use_container_width=True)
            except: 
                st.markdown("<h2 style='text-align: center;'>🥋 SER</h2>", unsafe_allow_html=True)
        
        st.write("") 
        
        # 2. ABAS (Login, Cadastro e agora Recuperação)
        tab_entrar, tab_cadastro, tab_recuperar = st.tabs(["🔐 Entrar", "📝 Criar Conta", "🔑 Esqueci a Senha"])

        # ===================================================
        # ABA 1: LOGIN
        # ===================================================
        with tab_entrar:
            c_l1, c_l2, c_l3 = st.columns([0.6, 0.8, 0.6])
            with c_l2:
                with st.container(border=True):
                    st.markdown("### Bem-vindo")
                    with st.form("login_form"):
                        email = st.text_input("E-mail").strip().lower()
                        senha = st.text_input("Senha", type="password")
                        
                        if st.form_submit_button("Acessar", use_container_width=True):
                            user_res = db.executar_query("SELECT * FROM usuarios WHERE email=%s AND senha=%s", (email, senha), fetch=True)
                            
                            if user_res:
                                user = user_res[0]
                                if user['status_conta'] == 'Ativo':
                                    st.session_state.logado = True
                                    st.session_state.usuario = dict(user)
                                    st.session_state.sidebar_state = 'expanded'
                                    st.success(f"Olá, {user['nome_completo']}!")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.warning("🔒 Conta em análise.")
                            else:
                                st.error("❌ E-mail ou senha incorretos.")

        # ===================================================
        # ABA 2: AUTO-CADASTRO
        # ===================================================
        with tab_cadastro:
            with st.container(border=True):
                st.info("Preencha para solicitar acesso à sua unidade.")
                filiais = db.executar_query("SELECT id, nome FROM filiais ORDER BY nome", fetch=True)
                opts_filial = {f['nome']: f['id'] for f in filiais} if filiais else {}
                
                c1, c2, c3 = st.columns(3)
                filial_selecionada = c1.selectbox("📍 Unidade", list(opts_filial.keys()) if opts_filial else ["Nenhuma"])
                nome = c2.text_input("Nome Completo")
                zap = c3.text_input("WhatsApp")
                
                c4, c5, c6 = st.columns(3)
                nasc = c4.date_input("Nascimento", value=date(2000, 1, 1), min_value=date(1920, 1, 1), max_value=date.today())
                email_novo = c5.text_input("E-mail (Login)")
                
                idade = utils.calcular_idade_ano(nasc)
                is_kid = idade < 16
                with c6:
                    if is_kid: st.warning(f"👶 Kids ({idade} anos)")
                    else: st.success(f"🥋 Adulto ({idade} anos)")

                c7, c8, c9 = st.columns(3)
                senha_nova = c7.text_input("Crie uma Senha", type="password")
                senha_conf = c8.text_input("Confirme a Senha", type="password")
                
                nm_resp, tel_resp = None, None
                if is_kid:
                    nm_resp = c9.text_input("Nome do Responsável")
                    tel_resp = st.text_input("WhatsApp do Responsável")

                st.markdown("---")
                c10, c11, c12 = st.columns(3)
                faixa = c10.selectbox("Sua Faixa Atual", utils.ORDEM_FAIXAS)
                graus = c11.selectbox("Quantos Graus?", [0, 1, 2, 3, 4])
                dt_inicio = c12.date_input("Início nos Treinos", value=date.today())
                
                c13, c14, c15 = st.columns(3)
                dt_faixa = c13.date_input("Data da Faixa Atual", value=date.today())
                
                dt_ultimo_grau = None
                if graus > 0:
                    dt_ultimo_grau = c14.date_input(f"Data do {graus}º Grau", value=date.today())

                if st.button("✅ Solicitar Cadastro", type="primary", use_container_width=True):
                    if not nome or not email_novo or not senha_nova:
                        st.error("Campos obrigatórios vazios.")
                    elif senha_nova != senha_conf:
                        st.error("As senhas não conferem.")
                    else:
                        data_referencia_grau = dt_ultimo_grau if graus > 0 else dt_faixa
                        id_filial = opts_filial.get(filial_selecionada)
                        res = db.executar_query(
                            """INSERT INTO usuarios 
                            (nome_completo, email, senha, telefone, data_nascimento, faixa, graus, 
                            id_filial, perfil, status_conta, data_inicio, data_ultimo_grau, 
                            nome_responsavel, telefone_responsavel) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'aluno', 'Pendente', %s, %s, %s, %s)""",
                            (nome, email_novo, senha_nova, zap, nasc, faixa, graus, id_filial, 
                             dt_inicio, data_referencia_grau, nm_resp, tel_resp)
                        )
                        if res == "ERRO_DUPLICADO": st.error("❌ E-mail já cadastrado.")
                        elif res:
                            st.success("✅ Solicitação enviada!"); time.sleep(2); st.rerun()

        # ===================================================
        # ABA 3: RECUPERAR SENHA (OPÇÃO 2)
        # ===================================================
        with tab_recuperar:
            c_r1, c_r2, c_r3 = st.columns([0.6, 0.8, 0.6])
            with c_r2:
                with st.container(border=True):
                    st.markdown("### Recuperar Acesso")
                    st.caption("Confirme seu e-mail e nascimento para criar uma nova senha.")
                    
                    with st.form("form_esqueci_senha"):
                        rec_email = st.text_input("E-mail cadastrado").strip().lower()
                        rec_nasc = st.date_input("Sua Data de Nascimento", value=date(2000, 1, 1), min_value=date(1920, 1, 1), max_value=date.today())
                        
                        st.markdown("---")
                        nova_s = st.text_input("Nova Senha", type="password")
                        nova_s_conf = st.text_input("Confirme a Nova Senha", type="password")
                        
                        if st.form_submit_button("Redefinir Senha", use_container_width=True):
                            if nova_s != nova_s_conf:
                                st.error("As senhas não conferem.")
                            elif len(nova_s) < 4:
                                st.error("A senha deve ser mais forte.")
                            else:
                                # Verifica se o usuário existe com esses dois dados
                                check = db.executar_query(
                                    "SELECT id FROM usuarios WHERE email=%s AND data_nascimento=%s",
                                    (rec_email, rec_nasc), fetch=True
                                )
                                
                                if check:
                                    # Atualiza
                                    sucesso = db.executar_query(
                                        "UPDATE usuarios SET senha=%s WHERE id=%s",
                                        (nova_s, check[0]['id'])
                                    )
                                    if sucesso:
                                        st.success("✅ Senha alterada! Agora você já pode entrar.")
                                        time.sleep(2)
                                        st.rerun()
                                else:
                                    st.error("❌ Dados não conferem. Se persistir, fale com seu professor.")