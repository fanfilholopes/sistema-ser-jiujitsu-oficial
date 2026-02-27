import streamlit as st
import psycopg2
import psycopg2.extras
from psycopg2 import pool

# --- POOL DE CONEXÃO COM CACHE (O SEGREDO DA VELOCIDADE) ---
# O @st.cache_resource garante que o Pool seja criado apenas UMA vez e fique na memória
@st.cache_resource
def get_pool():
    try:
        # Cria um pool que mantém de 1 a 20 conexões abertas, prontas para uso
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
    
    # Pega uma conexão "emprestada" do pool (super rápido, não precisa logar de novo)
    conn = db_pool.getconn()
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                # Retorna os dados e copia para uma lista para não depender do cursor aberto
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
        # Devolve a conexão para o pool para que outro usuário possa usar
        db_pool.putconn(conn)

# --- SETUP INICIAL (CRIAÇÃO DE TABELAS) ---
def setup_database():
    queries = [
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
            mensagem TEXT,
            data_criacao DATE DEFAULT CURRENT_DATE,
            ativo BOOLEAN DEFAULT TRUE
        );""",
        "ALTER TABLE turmas ADD COLUMN IF NOT EXISTS responsavel TEXT;",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS data_inicio DATE DEFAULT CURRENT_DATE;"
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