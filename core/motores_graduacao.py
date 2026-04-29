# core/motores_graduacao.py
from datetime import date
from core.config_graduacao import FAIXAS_KIDS
from core.formatters import calcular_idade_ano

# =======================================================
# LÓGICA PARA ADULTOS (16 ANOS OU MAIS) - REGRAS DE TEMPO
# =======================================================
def _calcular_progresso_adulto(aluno, presencas_no_periodo):
    faixa = aluno.get('faixa', 'Branca')
    graus = aluno.get('graus') or 0
    # Data base: Prioriza último grau, senão data de início
    data_base = aluno.get('data_ultimo_grau') or aluno.get('data_inicio') or date.today()
    
    # REGRAS DE CARÊNCIA DE TEMPO (MESES)
    if faixa == 'Branca':
        meses_carencia_grau = 3  # Branca de 3 em 3 meses
        carencia_faixa_total_meses = 12 
    elif faixa in ['Azul', 'Roxa', 'Marrom']:
        meses_carencia_grau = 6  # Azul até Marrom de 6 em 6 meses
        carencia_faixa_total_meses = 24 
    elif faixa == 'Preta':
        # Regra IBJJF: 3 anos (36 meses) para os 3 primeiros, 5 anos (60 meses) para o restante
        meses_carencia_grau = 36 if graus < 3 else 60
        carencia_faixa_total_meses = 360 
    else: 
        return False, "Faixa Inválida", False

    delta_tempo = date.today() - data_base
    dias_passados = delta_tempo.days
    
    # Verifica se atingiu o limite de 4 graus (Regra de indicação para exame)
    # A faixa preta não entra na lógica de 'Pronto p/ Exame' da mesma forma
    is_apto_faixa = (graus >= 4) and (faixa != 'Preta')
    
    # Define o alvo de tempo conforme o estado atual
    # Se já tem 4 graus, o sistema olha se ele já tem o tempo total na cor para trocar de faixa
    meses_alvo = carencia_faixa_total_meses if is_apto_faixa else meses_carencia_grau
    dias_necessarios = meses_alvo * 30
    
    # Validação exclusivamente por TEMPO para Adultos
    tempo_ok = dias_passados >= dias_necessarios

    if tempo_ok:
        if is_apto_faixa:
            # Novo status refinado conforme seu pedido
            msg = "🏆 Apto a ser indicado p/ Exame"
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
# LÓGICA PARA KIDS (MENORES DE 16 ANOS) - MANTIDA ORIGINAL
# =======================================================
def _calcular_progresso_kids(aluno, presencas_no_periodo):
    faixa = aluno.get('faixa', 'Branca')
    graus = aluno.get('graus') or 0
    nasc = aluno.get('data_nascimento')
    idade_atleta = calcular_idade_ano(nasc)
    data_base = aluno.get('data_ultimo_grau') or aluno.get('data_inicio') or date.today()
    
    # Regra Kids: Mantém foco em 8 aulas para o grau
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

    delta_tempo = date.today() - data_base
    aulas_ok = presencas_no_periodo >= meta_aulas_grau
    
    limite_graus = 4 if faixa in ['Branca', 'Cinza/Branca'] else 11
    is_apto_faixa = (graus >= limite_graus)

    tempo_cor_ok = True
    idade_ok = True
    if is_apto_faixa:
        tempo_cor_ok = delta_tempo.days >= (meses_carencia_cor * 30)
        idade_ok = idade_atleta >= trava_idade

    status_apto = aulas_ok if not is_apto_faixa else (aulas_ok and tempo_cor_ok and idade_ok)
    
    if status_apto:
        msg = f"Apto p/ {graus + 1}º Grau" if not is_apto_faixa else "Apto p/ Troca de Faixa"
    else:
        if not aulas_ok:
            msg = f"Faltam {int(meta_aulas_grau - presencas_no_periodo)} aulas"
        elif is_apto_faixa and not idade_ok:
            msg = f"Mínimo {trava_idade} anos"
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
    
    # Transição Juvenil automática aos 16 anos
    faixas_kids_coloridas = [f for f in FAIXAS_KIDS if f != 'Branca']
    if idade >= 16 and faixa in faixas_kids_coloridas:
        return True, "Apto p/ Juvenil (Mudar Faixa)", True
        
    if idade < 16:
        return _calcular_progresso_kids(aluno, presencas_no_periodo)
    else:
        return _calcular_progresso_adulto(aluno, presencas_no_periodo)