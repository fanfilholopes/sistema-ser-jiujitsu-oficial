import streamlit as st
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from datetime import date

# --- POOL DE CONEXÃO COM CACHE ---
@st.cache_resource
def get_pool():
    try:
        return psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=st.secrets["postgres"]["host"],
            database=st.secrets["postgres"]["database"],
            user=st.secrets["postgres"]["user"],
            password=st.secrets["postgres"]["password"],
            port=st.secrets["postgres"]["port"],
            sslmode="require"
        )
    except Exception as e:
        st.error(f"Erro grave ao criar o pool de conexão: {e}")
        return None

# --- EXECUTOR DE QUERIES ---
def executar_query(query, params=None, fetch=False):
    db_pool = get_pool()
    if not db_pool:
        return None
    
    conn = db_pool.getconn()
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                resultados = cur.fetchall()
                return resultados
            else:
                conn.commit()
                return True
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return "ERRO_DUPLICADO"
    except Exception as e:
        conn.rollback()
        st.error(f"Erro SQL: {e}")
        return None
    finally:
        db_pool.putconn(conn)

# =======================================================
# --- FUNÇÕES ESPECIALIZADAS EM GRADUAÇÃO (RESETS) ---
# =======================================================

def registrar_grau_direto(id_aluno, id_professor=None):
    """
    Executa o Reset Automático de Grau:
    1. Sobe +1 na contagem de graus do aluno.
    2. Atualiza a data_ultimo_grau para 'Hoje' (Zera o cronômetro de aulas).
    3. Salva no histórico de graduações.
    """
    # Busca dados atuais para o histórico
    aluno = executar_query("SELECT faixa, graus FROM usuarios WHERE id=%s", (id_aluno,), fetch=True)
    if aluno:
        faixa_atual = aluno[0]['faixa']
        novo_grau = aluno[0]['graus'] + 1
        
        # 1 e 2. Atualiza Usuário
        sql_user = "UPDATE usuarios SET graus = %s, data_ultimo_grau = CURRENT_DATE WHERE id = %s"
        executar_query(sql_user, (novo_grau, id_aluno))
        
        # 3. Salva Histórico
        sql_hist = """
            INSERT INTO historico_graduacoes (id_aluno, faixa, grau, data_graduacao, id_professor) 
            VALUES (%s, %s, %s, CURRENT_DATE, %s)
        """
        executar_query(sql_hist, (id_aluno, faixa_atual, novo_grau, id_professor))
        return True
    return False

def registrar_nova_faixa(id_aluno, nova_faixa, manter_graus=False, id_professor=None):
    """
    Executa a Troca de Cor (Reset de Faixa):
    1. Muda a cor da faixa.
    2. Zera os graus (salvo se manter_graus=True por mérito competitivo).
    3. Atualiza data_ultimo_grau para 'Hoje'.
    4. Salva no histórico.
    """
    graus_finais = 0
    if manter_graus:
        res = executar_query("SELECT graus FROM usuarios WHERE id=%s", (id_aluno,), fetch=True)
        graus_finais = res[0]['graus'] if res else 0

    # Atualiza Usuário
    sql_user = "UPDATE usuarios SET faixa = %s, graus = %s, data_ultimo_grau = CURRENT_DATE WHERE id = %s"
    executar_query(sql_user, (nova_faixa, graus_finais, id_aluno))
    
    # Salva Histórico
    sql_hist = """
        INSERT INTO historico_graduacoes (id_aluno, faixa, grau, data_graduacao, id_professor) 
        VALUES (%s, %s, %s, CURRENT_DATE, %s)
    """
    executar_query(sql_hist, (id_aluno, nova_faixa, graus_finais, id_professor))
    return True

# --- SETUP INICIAL ---
def setup_database():
    queries = [
        # Tabela de Check-ins (Frequência)
        """CREATE TABLE IF NOT EXISTS checkins (
            id SERIAL PRIMARY KEY,
            id_aluno INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
            id_turma INTEGER,
            id_filial INTEGER,
            data_aula DATE DEFAULT CURRENT_DATE,
            validado BOOLEAN DEFAULT FALSE,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""",
        
        # Tabela de Histórico de Graduações
        """CREATE TABLE IF NOT EXISTS historico_graduacoes (
            id SERIAL PRIMARY KEY,
            id_aluno INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
            faixa VARCHAR(50),
            grau INTEGER,
            data_graduacao DATE DEFAULT CURRENT_DATE,
            id_professor INTEGER
        );""",

        # Tabela de Solicitações (Fluxo de Faixa)
        """CREATE TABLE IF NOT EXISTS solicitacoes_graduacao (
            id SERIAL PRIMARY KEY,
            id_aluno INT,
            id_filial INT,
            faixa_atual TEXT,
            nova_faixa TEXT,
            data_solicitacao DATE DEFAULT CURRENT_DATE,
            status TEXT DEFAULT 'Pendente' 
        );""",
        
        # Tabela de Avisos
        """CREATE TABLE IF NOT EXISTS avisos (
            id SERIAL PRIMARY KEY,
            titulo TEXT,
            mensagem TEXT,
            data_postagem DATE DEFAULT CURRENT_DATE,
            publico_alvo TEXT DEFAULT 'Todos',
            ativo BOOLEAN DEFAULT TRUE
        );""",
        
        # Atualizações de Colunas Necessárias
        "ALTER TABLE turmas ADD COLUMN IF NOT EXISTS responsavel TEXT;",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS data_inicio DATE DEFAULT CURRENT_DATE;",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS data_ultimo_grau DATE;",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS foto_perfil TEXT;"
    ]
    
    db_pool = get_pool()
    if db_pool:
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                for q in queries:
                    try: 
                        cur.execute(q)
                    except: 
                        conn.rollback()
                conn.commit()
        except: 
            pass
        finally: 
            db_pool.putconn(conn)