# core/motores_graduacao.py
from datetime import date
from core.config_graduacao import FAIXAS_KIDS
from core.formatters import calcular_idade_ano

# =======================================================
# LÓGICA PARA ADULTOS (16 ANOS OU MAIS) - EXCLUSIVO POR TEMPO
# =======================================================
def _calcular_progresso_adulto(aluno, presencas_no_periodo):
    faixa = aluno.get('faixa', 'Branca')
    graus = aluno.get('graus') or 0
    
    # Datas de referência
    data_ultimo_grau = aluno.get('data_ultimo_grau')
    data_inicio = aluno.get('data_inicio') or date.today()
    
    # Para graus: conta a partir do último grau ou data de início
    data_base_grau = data_ultimo_grau or data_inicio
    
    # REGRAS DE CARÊNCIA DE TEMPO (MESES)
    if faixa == 'Branca':
        meses_carencia_grau = 3     
        carencia_faixa_total_meses = 12  
    elif faixa == 'Azul':
        meses_carencia_grau = 6     
        carencia_faixa_total_meses = 24  
    elif faixa == 'Roxa':
        meses_carencia_grau = 4.5   
        carencia_faixa_total_meses = 18  
    elif faixa == 'Marrom':
        meses_carencia_grau = 3     
        carencia_faixa_total_meses = 12  
    elif faixa == 'Preta':
        meses_carencia_grau = 36 if graus < 3 else 60
        carencia_faixa_total_meses = 360 
    else: 
        return False, "Faixa Inválida", False

    # Limite de Graus é 4 para as faixas coloridas e branca de adultos
    is_apto_faixa = (graus >= 4) and (faixa != 'Preta')
    
    if is_apto_faixa:
        delta_tempo = date.today() - data_inicio
        dias_passados = delta_tempo.days
        dias_necessarios = int(carencia_faixa_total_meses * 30.4167) 
    else:
        delta_tempo = date.today() - data_base_grau
        dias_passados = delta_tempo.days
        dias_necessarios = int(meses_carencia_grau * 30.4167)

    tempo_ok = dias_passados >= dias_necessarios

    if tempo_ok:
        if is_apto_faixa:
            msg = "🏆 Pronto p/ Exame"
            apto = True
        else:
            msg = f"Apto p/ {graus + 1}º Grau"
            apto = True
    else:
        restante_dias = dias_necessarios - dias_passados
        if restante_dias > 30:
            meses_f = (restante_dias // 30) + 1
            msg = f"Tempo: faltam aprox. {meses_f} mês(es)"
        else:
            msg = f"Tempo: faltam {restante_dias} dias"
        apto = False

    return apto, msg, is_apto_faixa

# =======================================================
# LÓGICA PARA KIDS (MENORES DE 16 ANOS)
# =======================================================

def _calcular_progresso_kids(aluno, presencas_no_periodo):
    faixa = aluno.get('faixa', 'Branca')
    graus = aluno.get('graus') or 0
    nasc = aluno.get('data_nascimento')
    idade_atleta = calcular_idade_ano(nasc)
    
    data_ultimo_grau = aluno.get('data_ultimo_grau')
    data_inicio = aluno.get('data_inicio') or date.today()
    
    meta_aulas_grau = 8 
    
    if faixa in ['Branca', 'Cinza/Branca']:
        meses_carencia_cor, trava_idade = 6, 0
    else:
        meses_carencia_cor = 12
        if 'Cinza' in faixa: trava_idade = 4
        elif 'Amarela' in faixa: trava_idade = 7
        elif 'Laranja' in faixa: trava_idade = 10
        elif 'Verde' in faixa: trava_idade = 13
        else: trava_idade = 0

    aulas_ok = presencas_no_periodo >= meta_aulas_grau
    
    # Limite de Graus
    limite_graus = 5 if faixa in ['Branca', 'Cinza/Branca'] else 11
    is_apto_faixa = (graus >= limite_graus)

    if is_apto_faixa:
        data_base_tempo = data_inicio
    else:
        data_base_tempo = data_ultimo_grau or data_inicio

    delta_tempo = date.today() - data_base_tempo
    dias_passados = delta_tempo.days
    dias_necessarios_cor = meses_carencia_cor * 30

    tempo_cor_ok = True
    idade_ok = True
    if is_apto_faixa:
        tempo_cor_ok = dias_passados >= dias_necessarios_cor
        idade_ok = idade_atleta >= trava_idade

    # CORREÇÃO: Se atingiu o limite de graus, ignora a contagem de aulas para o exame.
    status_apto = aulas_ok if not is_apto_faixa else (tempo_cor_ok and idade_ok)
    
    if status_apto:
        if not is_apto_faixa:
            if graus >= 4:
                msg = f"Apto p/ {graus + 1}º Grau (Colorido)"
            else:
                msg = f"Apto p/ {graus + 1}º Grau"
        else:
            msg = "🏆 Pronto p/ Exame"
    else:
        # Se NÃO está no limite de graus, cobra aulas normalmente
        if not is_apto_faixa and not aulas_ok:
            msg = f"Faltam {int(meta_aulas_grau - presencas_no_periodo)} aulas"
        # Se JÁ ESTÁ no limite de graus, avisa o que está travando o exame (idade ou tempo)
        elif is_apto_faixa and not idade_ok:
            msg = f"Mínimo {trava_idade} anos"
        elif is_apto_faixa and not tempo_cor_ok:
            restante_dias = dias_necessarios_cor - dias_passados
            if restante_dias > 30:
                msg = f"Aguarde carência (aprox. {(restante_dias // 30) + 1} meses)"
            else:
                msg = f"Aguarde carência ({restante_dias} dias)"
        else:
            msg = "Aguarde carência"

    return status_apto, msg, is_apto_faixa

# =======================================================
# MOTOR PRINCIPAL (DIRECIONAMENTO)
# =======================================================
def calcular_status_graduacao(aluno, presencas_no_periodo=0):
    nasc = aluno.get('data_nascimento')
    if not nasc: return False, "Sem data nasc.", False
        
    idade = calcular_idade_ano(nasc)
    faixa = aluno.get('faixa', 'Branca')
    
    faixas_kids_coloridas = [f for f in FAIXAS_KIDS if f != 'Branca']
    if idade >= 16 and faixa in faixas_kids_coloridas:
        return True, "Apto p/ Juvenil (Mudar Faixa)", True
        
    if idade < 16:
        return _calcular_progresso_kids(aluno, presencas_no_periodo)
    else:
        return _calcular_progresso_adulto(aluno, presencas_no_periodo)