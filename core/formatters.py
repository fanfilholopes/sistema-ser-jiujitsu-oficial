# core/formatters.py
from datetime import date
import requests
import streamlit as st

CARGOS = {
    "aluno": "Aluno",
    "monitor": "Monitor",
    "professor": "Professor",
    "lider": "Líder / Mestre",
    "adm_filial": "Admin da Filial"
}

@st.cache_data(ttl=3600)
def calcular_idade_ano(data_nascimento):
    if not data_nascimento: return 0
    # Regra SJJI: Ano Corrente - Ano Nascimento
    hoje = date.today()
    return hoje.year - data_nascimento.year

def buscar_dados_cep(cep):
    """Consulta a API ViaCEP"""
    cep = str(cep).replace("-", "").replace(".", "").strip()
    if len(cep) != 8: return None
    try:
        url = f"https://viacep.com.br/ws/{cep}/json/"
        resposta = requests.get(url, timeout=5)
        if resposta.status_code == 200:
            dados = resposta.json()
            if "erro" not in dados:
                return {
                    "logradouro": dados.get("logradouro"),
                    "bairro": dados.get("bairro"),
                    "cidade": dados.get("localidade"),
                    "estado": dados.get("uf")
                }
    except: return None
    return None