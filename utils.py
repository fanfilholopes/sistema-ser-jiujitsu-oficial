import streamlit as st
import requests
from datetime import date

# --- CONSTANTES ---
ORDEM_FAIXAS = ["Branca", "Cinza", "Amarela", "Laranja", "Verde", "Azul", "Roxa", "Marrom", "Preta"]

CARGOS = {
    "aluno": "Aluno",
    "monitor": "Monitor",
    "professor": "Professor",
    "adm_filial": "Admin da Filial"
}

# --- FUNÇÕES DE NEGÓCIO ---
def get_proxima_faixa(faixa_atual):
    try:
        idx = ORDEM_FAIXAS.index(faixa_atual)
        if idx + 1 < len(ORDEM_FAIXAS): return ORDEM_FAIXAS[idx + 1]
    except: pass
    return faixa_atual

def calcular_status_graduacao(aluno, presencas):
    hoje = date.today()
    # Garante que data_nascimento existe ou usa uma padrão para não quebrar
    nasc = aluno.get('data_nascimento', date(2000,1,1))
    data_base = aluno.get('data_ultimo_grau') or aluno.get('data_inicio') or hoje
    
    faixa = aluno.get('faixa', 'Branca')
    graus = aluno.get('graus') or 0
    
    idade = (hoje - nasc).days // 365
    is_kid = idade < 16 

    if is_kid:
        meta = 8
        pronto = presencas >= meta
        msg = f"✅ {presencas}/{meta} aulas" if pronto else f"Faltam {max(0, meta - presencas)} aulas"
        return pronto, msg, min(presencas/meta, 1.0), False
    elif faixa == 'Preta':
        regras = {0: 3, 1: 3, 2: 3, 3: 5, 4: 5, 5: 5, 6: 7, 7: 7, 8: 10}
        anos = regras.get(graus, 99)
        dias_meta = anos * 365
        dias_passados = (hoje - data_base).days
        pronto = dias_passados >= dias_meta
        msg = f"✅ Tempo ok" if pronto else f"Falta tempo ({anos} anos)"
        return pronto, msg, min(dias_passados/dias_meta, 1.0) if dias_meta > 0 else 0, False
    else:
        dias_meta = 180 
        dias_passados = (hoje - data_base).days
        pronto = dias_passados >= dias_meta
        troca = (graus >= 4)
        msg = f"✅ Apto" if pronto else f"Falta {(dias_meta - dias_passados)//30} meses"
        return pronto, msg, min(dias_passados/dias_meta, 1.0), troca

def buscar_dados_cep():
    """Callback para buscar CEP"""
    cep_digitado = st.session_state.get('cep_input_key', '')
    cep = str(cep_digitado).replace("-", "").replace(".", "").strip()
    if len(cep) == 8:
        try:
            r = requests.get(f"https://viacep.com.br/ws/{cep}/json/")
            if r.status_code == 200:
                dados = r.json()
                if "erro" not in dados:
                    # Atualiza o estado da sessão direto aqui
                    if 'form_filial' not in st.session_state:
                        st.session_state.form_filial = {}
                    st.session_state.form_filial['rua'] = dados.get('logradouro', '')
                    st.session_state.form_filial['bairro'] = dados.get('bairro', '')
                    st.session_state.form_filial['cidade'] = dados.get('localidade', '')
                    st.session_state.form_filial['uf'] = dados.get('uf', '')
                    st.toast("Endereço encontrado! 📍")
                else: st.toast("CEP não encontrado.")
        except: pass