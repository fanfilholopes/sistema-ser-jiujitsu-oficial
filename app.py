# app.py
import streamlit as st
import database as db
import views.login as login
import views.lider as lider
import views.admin as admin
import views.monitor as monitor
import views.aluno as aluno
import views.professor as professor
from datetime import date
import time

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
# Inicializamos o estado de login se não existir
if 'logado' not in st.session_state: 
    st.session_state.logado = False

# Definimos o estado inicial da sidebar: colapsada se não estiver logado
st.set_page_config(
    page_title="SER Jiu-Jitsu Official", 
    page_icon="🥋", 
    layout="wide", 
    initial_sidebar_state="collapsed" if not st.session_state.logado else "expanded"
)

# --- 2. CSS GLOBAL (REMOÇÃO DA SIDEBAR E IDENTIDADE VISUAL) ---
# Se não estiver logado, aplicamos o CSS que mata a sidebar e centraliza o conteúdo
css_customizado = ""
if not st.session_state.logado:
    css_customizado = """
    <style>
        /* Remove completamente a sidebar cinza e o botão de abrir */
        [data-testid="stSidebar"] {
            display: none;
        }
        [data-testid="stSidebarNav"] {
            display: none;
        }
        /* Ajusta a área principal para centralizar o formulário de 3 colunas */
        .main .block-container {
            max-width: 1000px; 
            margin: 0 auto;
            padding-top: 2rem;
        }
    </style>
    """

st.markdown(f"""
{css_customizado}
<style>
    /* Estilização de Métricas (Cards de Resumo) */
    div[data-testid="stMetric"] {{ 
        background-color: #1E1E1E; 
        border: 1px solid #333; 
        padding: 15px; 
        border-radius: 10px; 
        text-align: center; 
        box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
    }}
    /* Boxes de Alerta Customizados (Identidade SER) */
    .aviso-box {{ 
        background-color: #ffd700; 
        color: #000; 
        padding: 15px; 
        border-radius: 8px; 
        margin-bottom: 20px; 
        border-left: 8px solid #000; 
        font-weight: bold;
    }}
    /* Padronização de botões para ocupar largura total */
    .stButton > button {{
        width: 100%;
        border-radius: 5px;
        font-weight: bold;
    }}
</style>
""", unsafe_allow_html=True)

# --- 3. INICIALIZAÇÃO DO SISTEMA ---
if 'usuario' not in st.session_state: 
    st.session_state.usuario = None

# Garante a criação das tabelas no banco de dados
db.setup_database()

# --- 4. LÓGICA DE SINCRONIZAÇÃO DE DADOS ---
def atualizar_dados_sessao():
    """Mantém os dados do usuário atualizados (faixa, graus, etc) entre as navegações"""
    if st.session_state.logado and st.session_state.usuario:
        user_id = st.session_state.usuario['id']
        dados_atualizados = db.executar_query("SELECT * FROM usuarios WHERE id=%s", (user_id,), fetch=True)
        if dados_atualizados:
            st.session_state.usuario = dict(dados_atualizados[0])

# --- 5. ROTEAMENTO DE TELAS ---
if not st.session_state.logado:
    # Chama a tela de Login/Cadastro. 
    # Dentro de login.mostrar_login(), você deve usar st.columns(3) para os campos.
    login.mostrar_login()
else:
    # Se logado, sincroniza os dados e encaminha para o painel correspondente
    atualizar_dados_sessao()
    
    perfil = st.session_state.usuario['perfil']
    
    # Roteador de Perfis
    if perfil == 'lider': 
        lider.painel_lider()
        
    elif perfil == 'adm_filial': 
        admin.painel_adm_filial()
        
    elif perfil == 'professor': 
        professor.painel_professor()
        
    elif perfil == 'monitor': 
        monitor.painel_monitor()
        
    elif perfil == 'aluno': 
        aluno.painel_aluno()
        
    else:
        # Fallback para perfis não identificados
        st.error("Erro: Perfil de acesso não reconhecido.")
        if st.button("Tentar Novamente / Sair"):
            st.session_state.logado = False
            st.rerun()

# --- 6. RODAPÉ DE VERSÃO (VISÍVEL APENAS NA SIDEBAR APÓS LOGIN) ---
if st.session_state.logado:
    st.sidebar.divider()
    st.sidebar.caption(f"v3.0.0 - SER Jiu-Jitsu © {date.today().year}")