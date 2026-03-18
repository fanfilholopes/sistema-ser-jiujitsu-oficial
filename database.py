import streamlit as st
import psycopg2
import psycopg2.extras
from psycopg2 import pool

# --- POOL DE CONEXÃO COM CACHE ---
@st.cache_resource
def get_pool():
    try:
        return psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=20,
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

# --- SETUP INICIAL (ATUALIZADO COM PRESENÇAS E HISTÓRICO) ---
def setup_database():
    queries = [
        # Tabela de Presenças Oficiais
        """CREATE TABLE IF NOT EXISTS presencas (
            id SERIAL PRIMARY KEY,
            id_aluno INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
            data_presenca DATE DEFAULT CURRENT_DATE,
            metodo VARCHAR(20),
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""",
        
        # Tabela de Histórico de Graduações
        """CREATE TABLE IF NOT EXISTS historico_graduacoes (
            id SERIAL PRIMARY KEY,
            id_aluno INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
            faixa VARCHAR(50),
            grau INTEGER,
            data_graduacao DATE DEFAULT CURRENT_DATE,
            id_professor INTEGER REFERENCES usuarios(id)
        );""",

        # Tabelas já existentes
        """CREATE TABLE IF NOT EXISTS solicitacoes_graduacao (
            id SERIAL PRIMARY KEY,
            id_aluno INT,
            id_filial INT,
            faixa_atual TEXT,
            nova_faixa TEXT,
            data_solicitacao DATE DEFAULT CURRENT_DATE,
            status TEXT DEFAULT 'Pendente' 
        );""",
        
        """CREATE TABLE IF NOT EXISTS avisos (
            id SERIAL PRIMARY KEY,
            titulo TEXT,
            mensagem TEXT,
            data_postagem DATE DEFAULT CURRENT_DATE,
            publico_alvo TEXT DEFAULT 'Todos',
            ativo BOOLEAN DEFAULT TRUE
        );""",
        
        "ALTER TABLE turmas ADD COLUMN IF NOT EXISTS responsavel TEXT;",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS data_inicio DATE DEFAULT CURRENT_DATE;",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS data_ultimo_grau DATE;"
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