import streamlit as st
import requests
from datetime import date

# --- CONSTANTES ---
ORDEM_FAIXAS = [
    # --- KIDS (4 a 15 Anos) ---
    'Branca',                 
    'Cinza/Branca', 'Cinza', 'Cinza/Preta',       
    'Amarela/Branca', 'Amarela', 'Amarela/Preta', 
    'Laranja/Branca', 'Laranja', 'Laranja/Preta', 
    'Verde/Branca', 'Verde', 'Verde/Preta',       
    
    # --- JUVENIL / ADULTO (16+ Anos) ---
    'Azul',
    'Roxa',
    'Marrom',
    'Preta',
    'Coral (Vermelha/Preta)',
    'Coral (Vermelha/Branca)',
    'Vermelha'
]

CARGOS = {
    "aluno": "Aluno",
    "monitor": "Monitor",
    "professor": "Professor",
    "lider": "Líder / Mestre",
    "adm_filial": "Admin da Filial"
}

# --- FUNÇÕES AUXILIARES ---

def calcular_idade_ano(data_nascimento):
    """Retorna a idade que o aluno completa no ano atual"""
    if not data_nascimento: return 0
    return date.today().year - data_nascimento.year

def get_proxima_faixa(faixa_atual, idade=0):
    """
    Retorna a próxima faixa considerando a idade.
    Pula faixas infantis se for adulto (16+).
    """
    # 1. Regras de Pulo para Adultos (16+)
    if idade >= 16:
        # Se for Branca Adulto -> Vai para Azul
        if faixa_atual == 'Branca':
            return 'Azul'
        
        # Se for Juvenil (faixa de criança) -> Vai para Azul
        faixas_kids = [
            'Cinza/Branca', 'Cinza', 'Cinza/Preta',
            'Amarela/Branca', 'Amarela', 'Amarela/Preta',
            'Laranja/Branca', 'Laranja', 'Laranja/Preta',
            'Verde/Branca', 'Verde', 'Verde/Preta'
        ]
        if faixa_atual in faixas_kids:
            return 'Azul'

    # 2. Sequência Padrão (Kids ou Adulto seguindo a ordem)
    try:
        idx = ORDEM_FAIXAS.index(faixa_atual)
        if idx + 1 < len(ORDEM_FAIXAS):
            return ORDEM_FAIXAS[idx + 1]
    except:
        pass
    return "Grau Máximo"


# --- LÓGICA DE GRADUAÇÃO ---
def calcular_status_graduacao(aluno, total_presencas=0):
    
    faixa = aluno.get('faixa', 'Branca')
    graus = aluno.get('graus') or 0
    data_base = aluno.get('data_ultimo_grau') or aluno.get('data_inicio') or date.today()
    nasc = aluno.get('data_nascimento') or date(2000, 1, 1)
    
    idade_ano = calcular_idade_ano(nasc)
    
    meses_necessarios = 0
    is_troca_faixa = False # True = Muda cor | False = Ganha grau
    regra_aplicada = "Adulto"
    
    # Usamos a nova função inteligente para saber o nome do próximo passo
    # Se for troca de faixa, pegamos a próxima cor correta
    # Se for grau, o nome é calculado abaixo
    proxima_cor = get_proxima_faixa(faixa, idade_ano) 

    # 1. LISTA DE FAIXAS KIDS COLORIDAS
    faixas_kids_coloridas = [
        'Cinza/Branca', 'Cinza', 'Cinza/Preta',
        'Amarela/Branca', 'Amarela', 'Amarela/Preta',
        'Laranja/Branca', 'Laranja', 'Laranja/Preta',
        'Verde/Branca', 'Verde', 'Verde/Preta'
    ]

    # A. JUVENIL (16 ANOS)
    if idade_ano >= 16 and faixa in faixas_kids_coloridas:
        return True, "Juvenil (16 anos): Apto para Faixa Azul!", 1.0, True

    # B. KIDS (< 16 ANOS)
    if idade_ano < 16:
        regra_aplicada = "Kids"
        is_troca_faixa = True 
        
        if faixa in ['Branca', 'Cinza/Branca']:
            meses_necessarios = 6
        elif faixa in faixas_kids_coloridas:
            meses_necessarios = 12
            # Barreiras de Idade
            if 'Amarela' in proxima_cor and idade_ano < 7:
                return False, f"Aguardando idade (7 anos) para Amarela", 0.0, True
            if 'Laranja' in proxima_cor and idade_ano < 10:
                return False, f"Aguardando idade (10 anos) para Laranja", 0.0, True
            if 'Verde' in proxima_cor and idade_ano < 13:
                return False, f"Aguardando idade (13 anos) para Verde", 0.0, True

    # C. ADULTO (>= 16 ANOS)
    else:
        if faixa == 'Branca':
            meses_necessarios = 3
            if graus >= 4: is_troca_faixa = True
        elif faixa in ['Azul', 'Roxa', 'Marrom']:
            meses_necessarios = 6
            if graus >= 4: is_troca_faixa = True
        elif faixa == 'Preta':
            if graus < 3: meses_necessarios = 36
            elif graus >= 3 and graus < 6: meses_necessarios = 60
            elif graus == 6: 
                meses_necessarios = 84
                is_troca_faixa = True
        elif 'Coral' in faixa:
            meses_necessarios = 84 if 'Preta' in faixa else 120
            is_troca_faixa = True
        elif faixa == 'Vermelha':
            return True, "Grau Máximo", 1.0, False

    # CÁLCULO FINAL DE TEMPO
    delta = date.today() - data_base
    meses_treinados = delta.days / 30.0
    if meses_necessarios == 0: meses_necessarios = 1 
    progresso = min(meses_treinados / meses_necessarios, 1.0)
    
    if is_troca_faixa:
        prox_passo_txt = f"ir para {proxima_cor}"
    else:
        prox_passo_txt = f"pegar {graus + 1}º grau"
    
    if meses_treinados >= meses_necessarios:
        return True, f"Apto para {prox_passo_txt}!", 1.0, is_troca_faixa
    else:
        restante = float(meses_necessarios) - meses_treinados
        msg = f"Faltam ~{restante:.1f} meses para {prox_passo_txt}" if regra_aplicada == "Kids" else f"Em carência (~{restante:.1f} meses restantes)"
        return False, msg, progresso, is_troca_faixa

# --- VIA CEP ---
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
                    if 'form_filial' not in st.session_state:
                        st.session_state.form_filial = {}
                    st.session_state.form_filial['rua'] = dados.get('logradouro', '')
                    st.session_state.form_filial['bairro'] = dados.get('bairro', '')
                    st.session_state.form_filial['cidade'] = dados.get('localidade', '')
                    st.session_state.form_filial['uf'] = dados.get('uf', '')
                    st.toast("Endereço encontrado! 📍")
        except: pass