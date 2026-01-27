import streamlit as st
import database as db
import views.login as login
import views.lider as lider
import views.admin as admin
import views.monitor as monitor
import views.aluno as aluno
import views.professor as professor

# --- CONFIGURAÇÃO ---
if 'sidebar_state' not in st.session_state: st.session_state.sidebar_state = 'expanded'
st.set_page_config(page_title="SER Official", page_icon="🥋", layout="wide", initial_sidebar_state=st.session_state.sidebar_state)

# --- CSS GLOBAL ---
st.markdown("""
<style>
    div[data-testid="stMetric"] { background-color: #262730; border: 1px solid #464b5c; padding: 15px; border-radius: 8px; text-align: center; }
    .aviso-box { background-color: #ffd700; color: #000; padding: 10px; border-radius: 5px; margin-bottom: 20px; border-left: 5px solid #ff4b4b; }
    .student-card { background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%); padding: 20px; border-radius: 15px; border: 1px solid #444; text-align: center; margin-bottom: 20px; }
    .faixa-tag { background-color: #333; color: #fff; padding: 5px 15px; border-radius: 20px; font-size: 14px; margin-top: 10px; display: inline-block; border: 1px solid #666; }
</style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO ---
if 'logado' not in st.session_state: st.session_state.logado = False
if 'usuario' not in st.session_state: st.session_state.usuario = None
db.setup_database()

# --- ROTEAMENTO ---
if not st.session_state.logado:
    login.mostrar_login()
else:
    p = st.session_state.usuario['perfil']
    
    if p == 'lider': 
        lider.painel_lider()
        
    elif p == 'adm_filial': 
        admin.painel_adm_filial()
        
    elif p == 'professor': 
        professor.painel_professor()
        
    elif p == 'monitor': 
        monitor.painel_monitor()
        
    elif p == 'aluno': 
        aluno.painel_aluno()
        
    else:
        # Fallback de segurança (manda para admin se não reconhecer)
        admin.painel_adm_filial()