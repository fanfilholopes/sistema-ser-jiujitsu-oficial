from datetime import datetime

class AvaliacaoItem:
    """Representa uma parte do exame (ex: Quedas, Solo, Defesa)"""
    def __init__(self, modulo, nota, avaliador, sede):
        self.modulo = modulo        # Ex: "Quedas Básicas"
        self.nota = nota            # Ex: "Aprovado"
        self.avaliador = avaliador  # Ex: "Fanfilho"
        self.sede = sede            # Ex: "Filial Sul"
        self.data_hora = datetime.now()

class ExameGraduacao:
    """O Exame completo que agrupa várias avaliações"""
    def __init__(self, aluno_id, faixa_alvo):
        self.aluno_id = aluno_id
        self.faixa_alvo = faixa_alvo  # Ex: "Faixa Azul"
        self.data_inicio = datetime.now()
        self.status = "Em Andamento"
        self.historico_avaliacoes = [] # Lista para guardar o passo a passo

    def registrar_progresso(self, modulo, nota, avaliador, sede):
        # Aqui está a mágica do histórico detalhado que você pediu
        nova_avaliacao = AvaliacaoItem(modulo, nota, avaliador, sede)
        self.historico_avaliacoes.append(nova_avaliacao)
        
        print(f"--> [LOG] {avaliador} avaliou '{modulo}' na {sede}: {nota}")

    def finalizar_exame(self):
        # Regra de negócio: Só aprova se não tiver pendências (exemplo simples)
        reprovacoes = [a for a in self.historico_avaliacoes if a.nota == "Reprovado"]
        
        if not reprovacoes:
            self.status = "Aprovado - Aguardando Homologação"
            self.data_fim = datetime.now()
            print(f"--> SUCESSO: Aluno {self.aluno_id} aprovado para {self.faixa_alvo}!")
            return True
        else:
            self.status = "Pendente - Refazer Módulos"
            print("--> ATENÇÃO: O aluno tem módulos reprovados.")
            return False

# --- SIMULAÇÃO DO USO (O que aconteceria no sistema real) ---

# 1. Cria o exame (ex: Aluno João vai tentar a Faixa Azul)
exame_joao = ExameGraduacao(aluno_id=1, faixa_alvo="Faixa Azul")

# 2. Primeira avaliação (na Matriz, com Fanfilho)
exame_joao.registrar_progresso("Quedas", "Aprovado", "Fanfilho", "Matriz")

# 3. Segunda avaliação (dias depois, na Filial, com outro instrutor)
exame_joao.registrar_progresso("Passagem de Guarda", "Aprovado", "Instrutor Pedro", "Filial Centro")

# 4. Finalização
exame_joao.finalizar_exame()