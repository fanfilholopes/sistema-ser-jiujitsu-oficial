import streamlit as st
import database as db
import utils
import time
from datetime import date

def mostrar_login():
    # --- LAYOUT: CRIAÇÃO DA COLUNA CENTRAL ---
    # Usamos [1, 0.8, 1] para deixar o meio mais estreito (tipo mobile)
    # Isso força o formulário a ficar "magrinho" no centro da tela
    col_esq, col_centro, col_dir = st.columns([1, 0.8, 1])

    # TUDO acontece dentro desta coluna do meio
    with col_centro:
        
        # 1. LOGO E TÍTULO
        c_logo_esq, c_logo_centro, c_logo_dir = st.columns([1, 2, 1])
        with c_logo_centro:
            try: st.image("logoser.jpg", use_container_width=True)
            except: st.markdown("<h2 style='text-align: center;'>🥋 SER</h2>", unsafe_allow_html=True)
        
        st.write("") # Espaço extra
        
        # 2. ABAS (Agora dentro da coluna central!)
        tab_entrar, tab_cadastro = st.tabs(["🔐 Entrar", "📝 Criar Conta"])

        # ===================================================
        # ABA 1: LOGIN
        # ===================================================
        with tab_entrar:
            with st.container(border=True):
                st.markdown("### Bem-vindo")
                with st.form("login_form"):
                    email = st.text_input("E-mail")
                    senha = st.text_input("Senha", type="password")
                    
                    st.write("")
                    if st.form_submit_button("Acessar", use_container_width=True):
                        user = db.executar_query("SELECT * FROM usuarios WHERE email=%s AND senha=%s", (email, senha), fetch=True)
                        if user:
                            if user[0]['status_conta'] == 'Ativo':
                                st.session_state.logado = True
                                st.session_state.usuario = dict(user[0])
                                st.session_state.sidebar_state = 'expanded'
                                st.rerun()
                            else:
                                st.warning("🔒 Conta em análise.")
                        else:
                            st.error("❌ Dados incorretos.")

        # ===================================================
        # ABA 2: AUTO-CADASTRO (DINÂMICO)
        # ===================================================
        with tab_cadastro:
            with st.container(border=True):
                st.info("Preencha para solicitar acesso.")

                filiais = db.executar_query("SELECT id, nome FROM filiais ORDER BY nome", fetch=True)
                opts_filial = {f['nome']: f['id'] for f in filiais} if filiais else {}
                
                # --- FORMULÁRIO INTERATIVO (SEM st.form para permitir atualização) ---
                
                # Filial
                filial_selecionada = st.selectbox("📍 Unidade", list(opts_filial.keys()) if opts_filial else ["Nenhuma"])
                
                st.markdown("---")
                
                # Dados Pessoais
                nome = st.text_input("Nome Completo")
                
                c_nasc, c_zap = st.columns(2)
                # O st.rerun automático ao mudar a data fará a lógica do Kids funcionar
                nasc = c_nasc.date_input("Nascimento", value=date(2000, 1, 1), min_value=date(1920, 1, 1), max_value=date.today())
                zap = c_zap.text_input("WhatsApp")
                
                # Lógica Kids
                idade = (date.today() - nasc).days // 365
                is_kid = idade < 16
                nm_resp, tel_resp = None, None

                if is_kid:
                    st.warning(f"👶 Menor ({idade} anos). Responsável:")
                    nm_resp = st.text_input("Nome Responsável")
                    tel_resp = st.text_input("Tel. Responsável")
                
                st.markdown("---")
                
                # Login
                email_novo = st.text_input("E-mail (Login)")
                c_s1, c_s2 = st.columns(2)
                senha_nova = c_s1.text_input("Senha", type="password")
                senha_conf = c_s2.text_input("Confirmar", type="password")
                
                st.markdown("---")
                
                # Vida Marcial
                c_faixa, c_grau = st.columns([1.5, 1])
                faixa = c_faixa.selectbox("Faixa", utils.ORDEM_FAIXAS)
                graus = c_grau.selectbox("Graus", [0, 1, 2, 3, 4])
                
                # Datas
                dt_inicio = st.date_input("Início dos Treinos", value=date.today())
                
                c_d1, c_d2 = st.columns(2)
                lbl_faixa = "Data da Faixa"
                dt_faixa = c_d1.date_input(lbl_faixa, value=date.today())

                dt_ultimo_grau = None
                if graus > 0:
                    dt_ultimo_grau = c_d2.date_input(f"Data {graus}º Grau", value=date.today())
                else:
                    c_d2.empty()

                st.write("")
                # Botão de Ação
                if st.button("✅ Criar Conta", type="primary", use_container_width=True):
                    # Validações
                    erro = False
                    if not filial_selecionada:
                        st.error("Selecione a filial."); erro = True
                    if not nome or not email_novo or not senha_nova:
                        st.error("Preencha nome, email e senha."); erro = True
                    if senha_nova != senha_conf:
                        st.error("As senhas não conferem."); erro = True
                    if is_kid and (not nm_resp or not tel_resp):
                        st.error("Dados do responsável obrigatórios."); erro = True
                    
                    if not erro:
                        # Lógica de Datas
                        data_grau_banco = dt_ultimo_grau if graus > 0 else dt_faixa
                        id_filial = opts_filial[filial_selecionada]
                        
                        # NOVA LÓGICA: Separando o Try do Rerun e status = Pendente
                        cadastrou = False
                        try:
                            db.executar_query(
                                """INSERT INTO usuarios 
                                (nome_completo, email, senha, telefone, data_nascimento, faixa, graus, id_filial, perfil, status_conta, data_inicio, data_graduacao, data_ultimo_grau, nome_responsavel, telefone_responsavel) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'aluno', 'Pendente', %s, %s, %s, %s, %s)""",
                                (nome, email_novo, senha_nova, zap, nasc, faixa, graus, id_filial, dt_inicio, dt_faixa, data_grau_banco, nm_resp, tel_resp)
                            )
                            cadastrou = True
                        except Exception as e:
                            st.error("❌ E-mail já cadastrado.")
                            
                        # O Rerun acontece livre, leve e solto aqui fora!
                        if cadastrou:
                            st.success("✅ Solicitação enviada! Aguarde a aprovação do seu professor.")
                            time.sleep(2)
                            st.rerun()