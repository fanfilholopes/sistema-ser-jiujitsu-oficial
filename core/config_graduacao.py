# core/config_graduacao.py

FAIXAS_KIDS = ['Branca', 'Cinza/Branca', 'Cinza', 'Cinza/Preta', 'Amarela/Branca', 'Amarela', 'Amarela/Preta', 'Laranja/Branca', 'Laranja', 'Laranja/Preta', 'Verde/Branca', 'Verde', 'Verde/Preta']
FAIXAS_ADULTO = ['Branca', 'Azul', 'Roxa', 'Marrom', 'Preta', 'Coral (Vermelha/Preta)', 'Coral (Vermelha/Branca)', 'Vermelha']
ORDEM_FAIXAS = list(dict.fromkeys(FAIXAS_KIDS + FAIXAS_ADULTO))

# Por enquanto, mantemos os seus valores atuais para não mudar a regra agora
KIDS_AULAS_POR_GRAU = 8
KIDS_MESES_CARENCIA = 1
ADULTO_BRANCA_AULAS = 24
ADULTO_BRANCA_MESES = 3
# ... e assim por diante