import streamlit as st
import requests
from datetime import date

# =======================================================
# --- DEFINIÇÃO OFICIAL DE FAIXAS (REGULAMENTO SER) ---
# =======================================================

FAIXAS_KIDS = [
    'Branca',                 
    'Cinza/Branca', 'Cinza', 'Cinza/Preta',       
    'Amarela/Branca', 'Amarela', 'Amarela/Preta', 
    'Laranja/Branca', 'Laranja', 'Laranja/Preta', 
    'Verde/Branca', 'Verde', 'Verde/Preta'
]

FAIXAS_ADULTO = [
    'Branca', 'Azul', 'Roxa', 'Marrom', 'Preta', 
    'Coral (Vermelha/Preta)', 'Coral (Vermelha/Branca)', 'Vermelha'
]

ORDEM_FAIXAS = list(dict.fromkeys(FAIXAS_KIDS + FAIXAS_ADULTO))

CARGOS = {
    "aluno": "Aluno",
    "monitor": "Monitor",
    "professor": "Professor",
    "lider": "Líder / Mestre",
    "adm_filial": "Admin da Filial"
}

# =======================================================
# --- FUNÇÕES AUXILIARES DE CÁLCULO ---
# =======================================================

def calcular_idade_ano(data_nascimento):
    """Fórmula SER/IBJJF: ANO CORRENTE - ANO DE NASCIMENTO"""
    if not data_nascimento: return 0
    return date.today().year - data_nascimento.year

def get_proxima_faixa_cor(faixa_atual, idade_atleta=0):
    """Retorna a próxima cor de faixa baseada na idade e sequência oficial"""
    if idade_atleta >= 16:
        if faixa_atual in FAIXAS_KIDS or faixa_atual == 'Branca': return 'Azul'
        if faixa_atual in FAIXAS_ADULTO:
            idx = FAIXAS_ADULTO.index(faixa_atual)
            return FAIXAS_ADULTO[idx + 1] if idx + 1 < len(FAIXAS_ADULTO) else "Grau Máximo"
    else:
        if faixa_atual in FAIXAS_KIDS:
            idx = FAIXAS_KIDS.index(faixa_atual)
            return FAIXAS_KIDS[idx + 1] if idx + 1 < len(FAIXAS_KIDS) else "Aguardando 16 anos (Azul)"
    return "Faixa Inválida"

# =======================================================
# --- LÓGICA DE GRADUAÇÃO (KIDS vs ADULTO) ---
# =======================================================

def calcular_status_graduacao(aluno, presencas_no_periodo=0):
    """
    Calcula aptidão baseada em ciclos de tempo/aulas desde a DATA DO ÚLTIMO GRAU.
    presencas_no_periodo: deve ser o count de aulas >= data_ultimo_grau.
    """
    faixa = aluno.get('faixa', 'Branca')
    graus = aluno.get('graus') or 0
    data_base = aluno.get('data_ultimo_grau') or aluno.get('data_inicio') or date.today()
    nasc = aluno.get('data_nascimento') or date(2000, 1, 1)
    idade_atleta = calcular_idade_ano(nasc)
    
    # Variáveis de controle
    meses_carencia = 0 
    aulas_alvo = 0 
    is_apto_exame_faixa = False 
    proxima_cor_nome = get_proxima_faixa_cor(faixa, idade_atleta)

    # ---------------------------------------------------
    # 1. REGRA KIDS (SJJII - 8 AULAS POR GRAU)
    # ---------------------------------------------------
    if idade_atleta < 16:
        aulas_alvo = 8 # A cada 8 aulas recebe um grau
        meses_carencia = 1 # Mínimo de 1 mês entre graus
        
        if faixa == 'Branca' and graus >= 4:
            is_apto_exame_faixa = True
            meses_carencia = 6 # Tempo mínimo total na faixa branca p/ trocar cor
        elif faixa in FAIXAS_KIDS and graus >= 11:
            is_apto_exame_faixa = True
            meses_carencia = 12 # Tempo mínimo total na cor p/ trocar
            
        # Travas de Idade (IBJJF)
        if is_apto_exame_faixa:
            if 'Amarela' in proxima_cor_nome and idade_atleta < 7:
                return False, "Mínimo 7 anos p/ Amarela", 0.0, True
            if 'Laranja' in proxima_cor_nome and idade_atleta < 10:
                return False, "Mínimo 10 anos p/ Laranja", 0.0, True
            if 'Verde' in proxima_cor_nome and idade_atleta < 13:
                return False, "Mínimo 13 anos p/ Verde", 0.0, True

    # ---------------------------------------------------
    # 2. REGRA ADULTO (CBJJ - TEMPO NA BRANCA)
    # ---------------------------------------------------
    else:
        # Transição Juvenil
        if faixa in FAIXAS_KIDS and faixa != 'Branca':
             return True, "Apto p/ Exame (Transição Juvenil)", 1.0, True

        if faixa == 'Branca':
            meses_carencia = 3 # Regra CBJJ: 3 meses por grau
            aulas_alvo = 24 # Média de 2 aulas por semana no período
            if graus >= 4: is_apto_exame_faixa = True
            
        elif faixa in ['Azul', 'Roxa', 'Marrom']:
            meses_carencia = 6 # Tempo mínimo entre graus nas coloridas
            aulas_alvo = 48
            if graus >= 4: is_apto_exame_faixa = True
            
        elif faixa == 'Preta':
            aulas_alvo = 100 
            if graus < 3: meses_carencia = 36
            elif graus < 6: meses_carencia = 60
            else: meses_carencia = 84

    # --- CÁLCULO DE PROGRESSO ---
    delta_tempo = date.today() - data_base
    car_tempo_dias = meses_carencia * 30
    
    prog_tempo = min(delta_tempo.days / car_tempo_dias, 1.0) if car_tempo_dias > 0 else 1.0
    prog_aulas = min(presencas_no_periodo / aulas_alvo, 1.0) if aulas_alvo > 0 else 1.0
    
    # O progresso unificado respeita ambos os critérios
    progresso_total = min(prog_tempo, prog_aulas)
    
    prox_txt = f"ir para {proxima_cor_nome}" if is_apto_exame_faixa else f"pegar {graus + 1}º grau"

    # --- VERIFICAÇÃO FINAL ---
    if delta_tempo.days >= car_tempo_dias and presencas_no_periodo >= aulas_alvo:
        return True, f"Apto para {prox_txt}!", 1.0, is_apto_exame_faixa
    else:
        if presencas_no_periodo < aulas_alvo:
            faltam = int(aulas_alvo - presencas_no_periodo)
            msg = f"Faltam {faltam} aulas p/ {prox_txt}"
        else:
            meses_restantes = max(1, int((car_tempo_dias - delta_tempo.days)/30))
            msg = f"Aguardando ~{meses_restantes} mês(es) p/ {prox_txt}"
        return False, msg, progresso_total, is_apto_exame_faixa

# --- VIA CEP ---
def buscar_dados_cep():
    cep_digitado = st.session_state.get('cep_input_key', '')
    cep = str(cep_digitado).replace("-", "").replace(".", "").strip()
    if len(cep) == 8:
        try:
            r = requests.get(f"https://viacep.com.br/ws/{cep}/json/")
            if r.status_code == 200:
                dados = r.json()
                if "erro" not in dados:
                    if 'form_filial' not in st.session_state: st.session_state.form_filial = {}
                    st.session_state.form_filial['rua'] = dados.get('logradouro', '')
                    st.session_state.form_filial['bairro'] = dados.get('bairro', '')
                    st.session_state.form_filial['cidade'] = dados.get('localidade', '')
                    st.session_state.form_filial['uf'] = dados.get('uf', '')
                    st.toast("Endereço encontrado! 📍")
        except: pass