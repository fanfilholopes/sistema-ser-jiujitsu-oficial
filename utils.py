# utils.py
import streamlit as st
import requests
from datetime import date

# 1. IMPORTAÇÕES DAS REGRAS (Vem da pasta CORE)
from core.formatters import CARGOS, calcular_idade_ano, buscar_dados_cep
from core.config_graduacao import FAIXAS_KIDS, FAIXAS_ADULTO, ORDEM_FAIXAS
from core.motores_graduacao import calcular_status_graduacao

# =======================================================
# --- FUNÇÕES DE NAVEGAÇÃO E UI ---
# =======================================================

def get_proxima_faixa_cor(faixa_atual, idade_atleta=0):
    """Retorna a próxima cor de faixa baseada na idade e sequência oficial"""
    if idade_atleta >= 16:
        if faixa_atual in FAIXAS_KIDS or faixa_atual == 'Branca': 
            return 'Azul'
        if faixa_atual in FAIXAS_ADULTO:
            try:
                idx = FAIXAS_ADULTO.index(faixa_atual)
                return FAIXAS_ADULTO[idx + 1] if idx + 1 < len(FAIXAS_ADULTO) else "Grau Máximo"
            except ValueError:
                return "Azul" # Fallback
    else:
        if faixa_atual in FAIXAS_KIDS:
            try:
                idx = FAIXAS_KIDS.index(faixa_atual)
                return FAIXAS_KIDS[idx + 1] if idx + 1 < len(FAIXAS_KIDS) else "Aguardando 16 anos (Azul)"
            except ValueError:
                return "Cinza/Branca" # Fallback
    return "Faixa Inválida"

# =======================================================
# --- LOGICA DE ENDEREÇO (Ajustada para st.session_state) ---
# =======================================================

def preencher_endereco_pelo_cep():
    """Chama a lógica do CORE e atualiza o estado do formulário no Streamlit"""
    cep_digitado = st.session_state.get('cep_input_key', '')
    dados = buscar_dados_cep(cep_digitado)
    
    if dados:
        if 'form_filial' not in st.session_state: 
            st.session_state.form_filial = {}
            
        st.session_state.form_filial['rua'] = dados['logradouro']
        st.session_state.form_filial['bairro'] = dados['bairro']
        st.session_state.form_filial['cidade'] = dados['cidade']
        st.session_state.form_filial['uf'] = dados['estado']
        st.toast("Endereço encontrado! 📍")
    else:
        st.error("CEP não encontrado ou erro na busca.")