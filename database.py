import streamlit as st
import psycopg2
import psycopg2.extras

# --- CONEXÃO COM O BANCO ---
def get_connection():
    try:
        return psycopg2.connect(
            host=st.secrets["postgres"]["host"],
            database=st.secrets["postgres"]["database"],
            user=st.secrets["postgres"]["user"],
            password=st.secrets["postgres"]["password"],
            port=st.secrets["postgres"]["port"],
            sslmode="require"
        )
    except Exception as e:
        st.error(f"Erro grave de conexão: {e}")
        return None

# --- EXECUTOR DE QUERIES ---
def executar_query(query, params=None, fetch=False):
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                return cur.fetchall()
            else:
                conn.commit()
                return True
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return "ERRO_DUPLICADO"
    except Exception as e:
        if conn: conn.rollback()
        st.error(f"Erro SQL: {e}")
        return None
    finally:
        if conn: conn.close()

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
    conn = get_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                for q in queries:
                    try: cur.execute(q)
                    except: conn.rollback()
            conn.commit()
        except: pass
        finally: conn.close()