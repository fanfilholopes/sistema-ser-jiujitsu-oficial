import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
import time
import requests
import plotly.express as px
from datetime import date, datetime, timedelta

# --- CONTROLE DE SESSÃO ---
if 'sidebar_state' not in st.session_state:
    st.session_state.sidebar_state = 'expanded'
if 'form_filial' not in st.session_state:
    st.session_state.form_filial = {"rua": "", "bairro": "", "cidade": "", "uf": "", "cep": ""}

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="SER Official", 
    page_icon="🥋", 
    layout="wide",
    initial_sidebar_state=st.session_state.sidebar_state
)

# --- ESTILIZAÇÃO CSS (DESIGN PREMIUM) ---
st.markdown("""
<style>
    div[data-testid="stMetric"] {
        background-color: #262730;
        border: 1px solid #464b5c;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
    }
    div[data-testid="stMetricLabel"] > label {
        font-size: 14px;
        color: #b0b3c5;
    }
    div[data-testid="stMetricValue"] {
        font-size: 28px;
        font-weight: bold;
        color: #ffffff;
    }
    .aviso-box {
        background-color: #ffd700;
        color: #000;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 20px;
        border-left: 5px solid #ff4b4b;
    }
    .status-badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- ESTADO DA SESSÃO ---
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'usuario' not in st.session_state:
    st.session_state.usuario = None
if 'aluno_editando' not in st.session_state:
    st.session_state.aluno_editando = None

# ==================================================
# 1. FUNÇÕES AUXILIARES
# ==================================================
def exibir_logo_sidebar():
    try: st.sidebar.image("logoser.jpg", width=150)
    except: st.sidebar.markdown("## 🥋 SER Jiu-Jitsu")
    st.sidebar.markdown("---")

def rodape_sidebar():
    st.sidebar.markdown("---")
    c1, c2 = st.sidebar.columns(2)
    if c1.button("Sair", use_container_width=True):
        st.session_state.logado = False
        st.session_state.sidebar_state = 'expanded'
        st.rerun()
    if c2.button("⏪ Ocultar", help="Modo Foco", use_container_width=True):
        st.session_state.sidebar_state = 'collapsed'
        st.rerun()

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
                    st.session_state.form_filial['rua'] = dados.get('logradouro', '')
                    st.session_state.form_filial['bairro'] = dados.get('bairro', '')
                    st.session_state.form_filial['cidade'] = dados.get('localidade', '')
                    st.session_state.form_filial['uf'] = dados.get('uf', '')
                    st.toast("Endereço encontrado! 📍")
                else: st.toast("CEP não encontrado.")
        except: pass

# ==================================================
# 2. CONEXÃO E SETUP
# ==================================================
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
        return None

def executar_query(query, params=None, fetch=False):
    conn = get_connection()
    if not conn:
        st.error("🔌 Erro de conexão com o banco.")
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

setup_database()

# ==================================================
# 3. LÓGICAS DE NEGÓCIO
# ==================================================
ORDEM_FAIXAS = ["Branca", "Cinza", "Amarela", "Laranja", "Verde", "Azul", "Roxa", "Marrom", "Preta"]
CARGOS = {
    "aluno": "Aluno",
    "monitor": "Monitor",
    "professor": "Professor",
    "adm_filial": "Admin da Filial"
}

def get_proxima_faixa(faixa_atual):
    try:
        idx = ORDEM_FAIXAS.index(faixa_atual)
        if idx + 1 < len(ORDEM_FAIXAS): return ORDEM_FAIXAS[idx + 1]
    except: pass
    return faixa_atual

def calcular_status_graduacao(aluno, presencas):
    hoje = date.today()
    nasc = aluno['data_nascimento']
    data_base = aluno['data_ultimo_grau'] or aluno['data_inicio'] or hoje
    
    faixa = aluno['faixa']
    graus = aluno['graus'] or 0
    idade = (hoje - nasc).days // 365
    is_kid = idade < 16 

    if is_kid:
        meta = 8
        pronto = presencas >= meta
        msg = f"✅ {presencas}/{meta} aulas" if pronto else f"⏳ {presencas}/{meta} aulas"
        return pronto, msg, min(presencas/meta, 1.0), False
    elif faixa == 'Preta':
        regras = {0: 3, 1: 3, 2: 3, 3: 5, 4: 5, 5: 5, 6: 7, 7: 7, 8: 10}
        anos = regras.get(graus, 99)
        dias_meta = anos * 365
        dias_passados = (hoje - data_base).days
        pronto = dias_passados >= dias_meta
        msg = f"✅ Tempo ok" if pronto else f"⏳ Aguardando tempo"
        return pronto, msg, min(dias_passados/dias_meta, 1.0) if dias_meta > 0 else 0, False
    else:
        dias_meta = 180 
        dias_passados = (hoje - data_base).days
        pronto = dias_passados >= dias_meta
        troca = (graus >= 4)
        acao = f"Mudar {get_proxima_faixa(faixa)}" if troca else "Próximo Grau"
        msg = f"✅ Apto: {acao}" if pronto else f"⏳ Falta {(dias_meta - dias_passados)//30} meses"
        return pronto, msg, min(dias_passados/dias_meta, 1.0), troca

# ==================================================
# 4. TELAS
# ==================================================
def tela_login():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        try: st.image("logoser.jpg", width=200)
        except: st.markdown("## 🥋 SER Jiu-Jitsu")
        with st.container(border=True):
            st.markdown("### Acesso Oficial")
            with st.form("login"):
                email = st.text_input("E-mail")
                senha = st.text_input("Senha", type="password")
                if st.form_submit_button("Entrar", use_container_width=True):
                    user = executar_query("SELECT * FROM usuarios WHERE email=%s AND senha=%s", (email, senha), fetch=True)
                    if user and user[0]['status_conta'] == 'Ativo':
                        st.session_state.logado = True
                        st.session_state.usuario = dict(user[0])
                        st.session_state.sidebar_state = 'expanded'
                        st.rerun()
                    else: st.error("Acesso negado.")

# --- LÍDER (MASTER + OPERACIONAL) ---
def painel_lider():
    user = st.session_state.usuario
    # O Líder também tem uma filial "Sede" vinculada no cadastro dele
    id_filial_sede = user['id_filial']

    exibir_logo_sidebar()
    st.sidebar.title("Painel Mestre 👑")
    st.sidebar.caption(f"Olá, {user['nome_completo']}")
    rodape_sidebar()
    
    # ESTRUTURA HÍBRIDA
    tab_global, tab_central_grad, tab_rede, tab_chamada, tab_grad_sede, tab_alunos, tab_turmas, tab_avisos = st.tabs([
        "📊 Visão Global", "🎓 Central de Graduações", "🏢 Rede de Filiais", "✅ Chamada (Sede)", "🥋 Graduações (Sede)", "👥 Alunos (Sede)", "📅 Turmas (Sede)", "📢 Avisos"
    ])
    
    # 1. VISÃO GLOBAL
    with tab_global:
        total_alunos = executar_query("SELECT COUNT(*) FROM usuarios WHERE status_conta='Ativo' AND perfil='aluno'", fetch=True)[0][0]
        total_filiais = executar_query("SELECT COUNT(*) FROM filiais", fetch=True)[0][0]
        aguardando_homol = executar_query("SELECT COUNT(*) FROM solicitacoes_graduacao WHERE status='Aguardando Homologacao'", fetch=True)[0][0]
        niver_hoje = executar_query("SELECT COUNT(*) FROM usuarios WHERE status_conta='Ativo' AND EXTRACT(MONTH FROM data_nascimento) = EXTRACT(MONTH FROM CURRENT_DATE) AND EXTRACT(DAY FROM data_nascimento) = EXTRACT(DAY FROM CURRENT_DATE)", fetch=True)[0][0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Alunos (Rede)", total_alunos)
        c2.metric("Filiais Ativas", total_filiais)
        
        lbl_homol = "✅ Homologação"
        if aguardando_homol > 0: lbl_homol = "⚠️ Assinar Faixas"
        c3.metric(lbl_homol, aguardando_homol)
        
        lbl_niver = "🎂 Niver Hoje"
        if niver_hoje > 0: lbl_niver = "🎉 Hoje é dia!"
        c4.metric(lbl_niver, niver_hoje)

        st.divider()
        col_global, col_sede = st.columns(2)
        with col_global:
            st.markdown("### 🌍 Rede Completa")
            with st.container(border=True):
                dados_rede = executar_query("SELECT faixa, COUNT(*) as qtd FROM usuarios WHERE perfil='aluno' AND status_conta='Ativo' GROUP BY faixa", fetch=True)
                if dados_rede:
                    df_rede = pd.DataFrame(dados_rede, columns=['Faixa', 'Qtd'])
                    fig_rede = px.pie(df_rede, values='Qtd', names='Faixa', title='Distribuição Global', hole=0.4)
                    st.plotly_chart(fig_rede, use_container_width=True)
                    st.dataframe(df_rede.set_index('Faixa'), use_container_width=True)
                else: st.info("Sem dados globais.")

        with col_sede:
            st.markdown("### 🏠 Sede / Matriz")
            with st.container(border=True):
                dados_sede = executar_query("SELECT faixa, COUNT(*) as qtd FROM usuarios WHERE perfil='aluno' AND status_conta='Ativo' AND id_filial=%s GROUP BY faixa", (id_filial_sede,), fetch=True)
                if dados_sede:
                    df_sede = pd.DataFrame(dados_sede, columns=['Faixa', 'Qtd'])
                    fig_sede = px.pie(df_sede, values='Qtd', names='Faixa', title='Distribuição Sede', hole=0.4)
                    st.plotly_chart(fig_sede, use_container_width=True)
                    st.dataframe(df_sede.set_index('Faixa'), use_container_width=True)
                else: st.info("Sem alunos na Sede.")

    # 2. CENTRAL DE GRADUAÇÕES (VISÃO MACRO - LÍDER)
    with tab_central_grad:
        st.subheader("🎓 Central de Homologação e Controle")
        
        # --- BLOCO 1: AÇÃO NECESSÁRIA (PENDENTES) ---
        st.markdown("#### ⏳ Aguardando sua Assinatura (Exame já aprovado)")
        pendentes = executar_query("""
            SELECT s.id, u.nome_completo, f.nome as filial, s.faixa_atual, s.nova_faixa, s.data_solicitacao, s.id_aluno
            FROM solicitacoes_graduacao s
            JOIN usuarios u ON s.id_aluno = u.id
            JOIN filiais f ON s.id_filial = f.id
            WHERE s.status = 'Aguardando Homologacao'
        """, fetch=True)
        
        if pendentes:
            st.warning(f"Você tem {len(pendentes)} faixas para homologar.")
            # Lista simples como pedido
            for p in pendentes:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    c1.markdown(f"**{p['nome_completo']}**")
                    c1.caption(f"{p['filial']}")
                    c2.markdown(f"{p['faixa_atual']} ➝ **{p['nova_faixa']}**")
                    if c3.button("✅ HOMOLOGAR", key=f"hom_lider_{p['id']}", use_container_width=True):
                        executar_query("UPDATE usuarios SET faixa=%s, graus=0, data_graduacao=CURRENT_DATE, data_ultimo_grau=CURRENT_DATE WHERE id=%s", (p['nova_faixa'], p['id_aluno']))
                        executar_query("UPDATE solicitacoes_graduacao SET status='Concluido' WHERE id=%s", (p['id'],))
                        st.balloons(); st.toast("Homologado com Sucesso!"); time.sleep(1); st.rerun()
        else:
            st.success("Tudo limpo! Nenhuma homologação pendente.")

        st.divider()
        
        # --- BLOCO 2: RADAR DA REDE (ACOMPANHAMENTO) ---
        st.markdown("#### 📡 Radar de Processos em Andamento (Rede)")
        acompanhamento = executar_query("""
            SELECT u.nome_completo, f.nome as filial, s.nova_faixa, s.status 
            FROM solicitacoes_graduacao s 
            JOIN usuarios u ON s.id_aluno=u.id 
            JOIN filiais f ON s.id_filial=f.id 
            WHERE s.status IN ('Pendente', 'Aguardando Exame', 'Aprovado_Filial')
            ORDER BY s.id DESC
        """, fetch=True)
        
        if acompanhamento:
            df_acomp = pd.DataFrame(acompanhamento, columns=['Aluno', 'Filial', 'Nova Faixa', 'Status Atual'])
            st.dataframe(df_acomp, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum processo em andamento nas filiais.")

    # 3. REDE DE FILIAIS (CADASTRO)
    with tab_rede:
        st.subheader("Gestão da Rede")
        
        with st.expander("➕ Nova Filial (Clique para abrir)", expanded=False):
            st.info("Preencha os dados abaixo. Use a lupa para buscar Responsável e Endereço.")
            users_db = executar_query("SELECT id, nome_completo FROM usuarios ORDER BY nome_completo", fetch=True)
            dict_users = {u['nome_completo']: u['id'] for u in users_db} if users_db else {}

            c1, c2, c3 = st.columns([2, 2, 2])
            nome_f = c1.text_input("Nome da Filial")
            tel_f = c2.text_input("Telefone da Filial")
            resp_select = c3.selectbox("Responsável (Buscar)", ["Selecione..."] + list(dict_users.keys()))
            
            st.divider()
            c_cep, c_rua, c_num = st.columns([2, 4, 1])
            cep_in = c_cep.text_input("CEP", key="cep_input_key", on_change=buscar_dados_cep, max_chars=8)
            rua_f = c_rua.text_input("Rua", value=st.session_state.form_filial['rua'])
            num_f = c_num.text_input("Nº")
            c_bairro, c_cid, c_uf = st.columns([2, 3, 1])
            bairro_f = c_bairro.text_input("Bairro", value=st.session_state.form_filial['bairro'])
            cidade_f = c_cid.text_input("Cidade", value=st.session_state.form_filial['cidade'])
            uf_f = c_uf.text_input("UF", value=st.session_state.form_filial['uf'])
            
            if st.button("Salvar Nova Filial", type="primary", use_container_width=True):
                if nome_f and resp_select != "Selecione...":
                    try:
                        executar_query("INSERT INTO filiais (nome, responsavel_nome, telefone_contato, endereco, numero, bairro, cidade, estado, cep) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", (nome_f, resp_select, tel_f, rua_f, num_f, bairro_f, cidade_f, uf_f, cep_in))
                        st.success("Filial Cadastrada!"); time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Erro: {e}")
                else: st.warning("Preencha Nome e Responsável.")

        st.divider()
        filiais = executar_query("SELECT * FROM filiais ORDER BY nome", fetch=True)
        if filiais:
            for f in filiais:
                q_alunos = executar_query("SELECT COUNT(*) FROM usuarios WHERE id_filial=%s AND status_conta='Ativo' AND perfil='aluno'", (f['id'],), fetch=True)[0][0]
                turmas_f = executar_query("SELECT nome, dias, horario FROM turmas WHERE id_filial=%s", (f['id'],), fetch=True)
                with st.expander(f"🏢 {f['nome']} ({f['cidade']}) - {q_alunos} Alunos"):
                    c_info, c_turmas = st.columns([1, 1])
                    with c_info:
                        st.write(f"👤 **Resp:** {f['responsavel_nome']}")
                        st.write(f"📞 {f['telefone_contato']}")
                        st.write(f"📍 {f['endereco']}, {f['numero']} - {f['bairro']}")
                    with c_turmas:
                        if turmas_f:
                            for t in turmas_f: st.code(f"{t['nome']} | {t['dias']} | {t['horario']}")
                        else: st.caption("Sem turmas.")

    # 4. CHAMADA (SEDE)
    with tab_chamada:
        st.subheader("Fazer Chamada (Sede)")
        c1, c2 = st.columns([1, 2])
        data_aula = c1.date_input("Data", date.today(), key="dt_lid")
        turmas = executar_query("SELECT id, nome FROM turmas WHERE id_filial=%s", (id_filial_sede,), fetch=True)
        d_turmas = {t['nome']: t['id'] for t in turmas} if turmas else {}
        sel_turma = c2.selectbox("Turma", list(d_turmas.keys()), key="tm_lid") if d_turmas else None
        
        if sel_turma:
            id_t = d_turmas[sel_turma]
            ja_veio = [x[0] for x in executar_query("SELECT id_aluno FROM checkins WHERE id_turma=%s AND data_aula=%s", (id_t, data_aula), fetch=True)]
            alunos = executar_query("SELECT id, nome_completo, faixa FROM usuarios WHERE id_turma=%s AND status_conta='Ativo' ORDER BY nome_completo", (id_t,), fetch=True)
            with st.form("ch_lider"):
                checks = []
                for a in alunos:
                    if st.checkbox(f"{a['nome_completo']} ({a['faixa']})", value=(a['id'] in ja_veio), key=f"cl_{a['id']}"): checks.append(a['id'])
                if st.form_submit_button("Salvar Chamada"):
                    executar_query("DELETE FROM checkins WHERE id_turma=%s AND data_aula=%s", (id_t, data_aula))
                    for uid in checks: executar_query("INSERT INTO checkins (id_aluno, id_turma, id_filial, data_aula) VALUES (%s, %s, %s, %s)", (uid, id_t, id_filial_sede, data_aula))
                    st.success("Salvo!"); time.sleep(0.5); st.rerun()

    # 5. GRADUAÇÕES SEDE (OPERACIONAL DO LÍDER) - NOVO!
    with tab_grad_sede:
        st.subheader("Gestão de Faixas (Sede)")
        
        # Alertas Operacionais da Sede
        pend_adm = executar_query("SELECT COUNT(*) FROM solicitacoes_graduacao WHERE id_filial=%s AND status='Pendente'", (id_filial_sede,), fetch=True)[0][0]
        pend_exame = executar_query("SELECT COUNT(*) FROM solicitacoes_graduacao WHERE id_filial=%s AND status='Aguardando Exame'", (id_filial_sede,), fetch=True)[0][0]
        
        if pend_adm > 0: st.error(f"⚠️ {pend_adm} Pendências Financeiras (Seus Alunos)")
        if pend_exame > 0: st.warning(f"🥋 {pend_exame} Aguardando Resultado de Exame (Seus Alunos)")

        # 1. Autorização Financeira (Sede)
        pendentes_sede = executar_query("SELECT s.id, u.nome_completo, s.nova_faixa FROM solicitacoes_graduacao s JOIN usuarios u ON s.id_aluno=u.id WHERE s.id_filial=%s AND s.status='Pendente'", (id_filial_sede,), fetch=True)
        if pendentes_sede:
            with st.container(border=True):
                st.markdown("#### 1. Autorizar Exame (Sede)")
                for p in pendentes_sede:
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"**{p['nome_completo']}** ➝ {p['nova_faixa']}")
                    if c2.button("Autorizar", key=f"aut_sed_{p['id']}"):
                        executar_query("UPDATE solicitacoes_graduacao SET status='Aguardando Exame' WHERE id=%s", (p['id'],))
                        st.rerun()

        # 2. Resultado de Exame (Sede)
        aguardando_sede = executar_query("SELECT s.id, u.nome_completo, s.nova_faixa FROM solicitacoes_graduacao s JOIN usuarios u ON s.id_aluno=u.id WHERE s.id_filial=%s AND s.status='Aguardando Exame'", (id_filial_sede,), fetch=True)
        if aguardando_sede:
            with st.container(border=True):
                st.markdown("#### 2. Registrar Resultado do Exame (Sede)")
                for e in aguardando_sede:
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"**{e['nome_completo']}** (Exame: {e['nova_faixa']})")
                    if c2.button("Aprovado ✅", key=f"ex_sed_{e['id']}"):
                        executar_query("UPDATE solicitacoes_graduacao SET status='Aguardando Homologacao' WHERE id=%s", (e['id'],))
                        st.toast("Enviado para Homologação!"); time.sleep(1); st.rerun()

        # 3. Radar / Indicação (Sede)
        st.markdown("#### 📡 Radar de Indicação (Sede)")
        alunos_sede = executar_query("SELECT id, nome_completo, faixa, graus, data_nascimento, data_ultimo_grau, data_inicio FROM usuarios WHERE id_filial=%s AND perfil='aluno' AND status_conta='Ativo' ORDER BY nome_completo", (id_filial_sede,), fetch=True)
        if alunos_sede:
            for a in alunos_sede:
                marco = a['data_ultimo_grau'] or a['data_inicio'] or date.today()
                pres = executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s AND data_aula >= %s", (a['id'], marco), fetch=True)[0][0]
                pronto, msg, prog, troca = calcular_status_graduacao(a, pres)
                
                with st.expander(f"{'🔥' if pronto else '⏳'} {a['nome_completo']} - {msg}"):
                    st.progress(prog)
                    c1, c2 = st.columns(2)
                    if c1.button("+1 Grau", key=f"g_sed_{a['id']}"):
                        executar_query("UPDATE usuarios SET graus = graus + 1, data_ultimo_grau = CURRENT_DATE WHERE id=%s", (a['id'],))
                        st.toast("Grau +1"); time.sleep(1); st.rerun()
                    if troca:
                        nf = get_proxima_faixa(a['faixa'])
                        status = executar_query("SELECT status FROM solicitacoes_graduacao WHERE id_aluno=%s AND status != 'Concluido'", (a['id'],), fetch=True)
                        if status: st.info(f"Em andamento: {status[0][0]}")
                        else:
                            if c2.button(f"INDICAR {nf} 🔼", key=f"ind_sed_{a['id']}"):
                                executar_query("INSERT INTO solicitacoes_graduacao (id_aluno, id_filial, faixa_atual, nova_faixa, status) VALUES (%s, %s, %s, %s, 'Pendente')", (a['id'], id_filial_sede, a['faixa'], nf))
                                st.success("Indicado!"); time.sleep(1); st.rerun()

    # 6. ALUNOS (SEDE)
    with tab_alunos:
        tab_l_lista, tab_l_novo = st.tabs(["📋 Meus Alunos", "➕ Matricular"])
        with tab_l_lista:
            if st.session_state.aluno_editando:
                aid = st.session_state.aluno_editando
                d = executar_query("SELECT * FROM usuarios WHERE id=%s", (aid,), fetch=True)[0]
                st.info(f"Editando: {d['nome_completo']}")
                with st.form("ed_lid"):
                    nm = st.text_input("Nome", value=d['nome_completo'])
                    pf = st.selectbox("Cargo", list(CARGOS.keys()), index=list(CARGOS.keys()).index(d['perfil']))
                    if st.form_submit_button("Salvar"):
                        executar_query("UPDATE usuarios SET nome_completo=%s, perfil=%s WHERE id=%s", (nm, pf, aid))
                        st.session_state.aluno_editando = None; st.rerun()
                    if st.form_submit_button("Cancelar"):
                        st.session_state.aluno_editando = None; st.rerun()
            else:
                meus_alunos = executar_query("SELECT id, nome_completo, faixa, perfil FROM usuarios WHERE id_filial=%s AND status_conta='Ativo' ORDER BY nome_completo", (id_filial_sede,), fetch=True)
                if meus_alunos: st.dataframe(pd.DataFrame(meus_alunos, columns=['ID', 'Nome', 'Faixa', 'Cargo']), use_container_width=True, hide_index=True)
        
        with tab_l_novo:
            turmas_sede = executar_query("SELECT id, nome FROM turmas WHERE id_filial=%s", (id_filial_sede,), fetch=True)
            opts_sede = {t['nome']: t['id'] for t in turmas_sede} if turmas_sede else {}
            with st.form("nv_lid"):
                n = st.text_input("Nome")
                e = st.text_input("Email")
                dn = st.date_input("Nascimento", date(2000,1,1), min_value=date(1920,1,1), max_value=date.today())
                tm = st.selectbox("Turma", list(opts_sede.keys())) if opts_sede else None
                if st.form_submit_button("Cadastrar"):
                    if tm:
                        executar_query("INSERT INTO usuarios (nome_completo, email, senha, data_nascimento, id_filial, id_turma, perfil, status_conta, faixa, graus) VALUES (%s, %s, '123', %s, %s, %s, 'aluno', 'Ativo', 'Branca', 0)", (n, e, dn, id_filial_sede, opts_sede[tm]))
                        st.success("Cadastrado!"); time.sleep(1); st.rerun()
                    else: st.error("Crie uma turma antes.")

    # 7. TURMAS (SEDE)
    with tab_turmas:
        c1, c2 = st.columns([1, 2])
        with c1:
            with st.form("nt_lid"):
                tn = st.text_input("Nome Turma")
                td = st.text_input("Dias")
                th = st.text_input("Horário")
                if st.form_submit_button("Criar"):
                    executar_query("INSERT INTO turmas (nome, dias, horario, responsavel, id_filial) VALUES (%s, %s, %s, '', %s)", (tn, td, th, id_filial_sede))
                    st.rerun()
        with c2:
            ts = executar_query("SELECT nome, dias, horario FROM turmas WHERE id_filial=%s", (id_filial_sede,), fetch=True)
            if ts: st.dataframe(pd.DataFrame(ts, columns=['Turma', 'Dias', 'Horário']), use_container_width=True)

    # 8. AVISOS
    with tab_avisos:
        st.subheader("📢 Comunicados para a Rede")
        with st.form("novo_aviso"):
            msg = st.text_area("Mensagem")
            if st.form_submit_button("Publicar Aviso Global"):
                executar_query("UPDATE avisos SET ativo=FALSE")
                executar_query("INSERT INTO avisos (mensagem, ativo) VALUES (%s, TRUE)", (msg,))
                st.success("Publicado!"); time.sleep(1); st.rerun()

# --- MONITOR ---
def painel_monitor():
    user = st.session_state.usuario
    exibir_logo_sidebar()
    st.sidebar.markdown(f"## Área do Monitor")
    st.sidebar.write(f"Olá, {user['nome_completo']}")
    rodape_sidebar()

    tab_chamada, tab_lista = st.tabs(["✅ Chamada", "👥 Alunos"])
    
    with tab_chamada:
        st.subheader("Auxiliar na Chamada")
        turmas = executar_query("SELECT id, nome FROM turmas WHERE id_filial=%s", (user['id_filial'],), fetch=True)
        d_turmas = {t['nome']: t['id'] for t in turmas} if turmas else {}
        sel_turma = st.selectbox("Turma", list(d_turmas.keys())) if d_turmas else None
        if sel_turma:
            id_t = d_turmas[sel_turma]
            alunos = executar_query("SELECT id, nome_completo FROM usuarios WHERE id_turma=%s AND status_conta='Ativo'", (id_t,), fetch=True)
            with st.form("chamada_mon"):
                checks = []
                for a in alunos:
                    if st.checkbox(a['nome_completo'], key=f"m_{a['id']}"): checks.append(a['id'])
                if st.form_submit_button("Salvar Chamada"):
                    executar_query("DELETE FROM checkins WHERE id_turma=%s AND data_aula=CURRENT_DATE", (id_t,))
                    for uid in checks: executar_query("INSERT INTO checkins (id_aluno, id_turma, id_filial, data_aula) VALUES (%s, %s, %s, CURRENT_DATE)", (uid, id_t, user['id_filial']))
                    st.success("Feito!"); time.sleep(0.5); st.rerun()
    with tab_lista:
        st.dataframe(pd.DataFrame(executar_query("SELECT nome_completo, faixa, telefone FROM usuarios WHERE id_filial=%s AND perfil='aluno'", (user['id_filial'],), fetch=True), columns=['Nome', 'Faixa', 'Zap']), use_container_width=True)

# --- PROFESSOR & ADMIN ---
def painel_adm_filial():
    user = st.session_state.usuario
    id_filial = user['id_filial']
    perfil = user['perfil']
    eh_admin = perfil == 'adm_filial'
    
    dados_filial = executar_query("SELECT nome FROM filiais WHERE id=%s", (id_filial,), fetch=True)
    nome_filial = dados_filial[0]['nome'] if dados_filial else "Filial"

    exibir_logo_sidebar()
    st.sidebar.markdown(f"## {nome_filial}")
    st.sidebar.write(f"Olá, **{user['nome_completo']}**")
    st.sidebar.caption(f"{CARGOS.get(perfil, perfil).upper()}")
    rodape_sidebar()

    tab_dash, tab_chamada, tab_graduacao, tab_turmas, tab_alunos = st.tabs(["📊 Painel", "✅ Chamada", "🎓 Graduações", "📅 Turmas", "👥 Equipe"])

    # 1. DASHBOARD PREMIUM
    with tab_dash:
        aviso = executar_query("SELECT mensagem FROM avisos WHERE ativo=TRUE ORDER BY id DESC LIMIT 1", fetch=True)
        if aviso:
            st.markdown(f"""<div class="aviso-box"><strong>📢 MENSAGEM DO MESTRE:</strong><br>{aviso[0]['mensagem']}</div>""", unsafe_allow_html=True)

        st.markdown(f"### 📅 {date.today().strftime('%d/%m/%Y')}")
        
        qtd = executar_query("SELECT COUNT(*) FROM usuarios WHERE id_filial=%s AND status_conta='Ativo' AND perfil='aluno'", (id_filial,), fetch=True)[0][0]
        qtd_turmas = executar_query("SELECT COUNT(*) FROM turmas WHERE id_filial=%s", (id_filial,), fetch=True)[0][0]
        treinos_hoje = executar_query("SELECT COUNT(*) FROM checkins WHERE id_filial=%s AND data_aula=CURRENT_DATE", (id_filial,), fetch=True)[0][0]
        
        pend_adm = executar_query("SELECT COUNT(*) FROM solicitacoes_graduacao WHERE id_filial=%s AND status='Pendente'", (id_filial,), fetch=True)[0][0]
        pend_exame = executar_query("SELECT COUNT(*) FROM solicitacoes_graduacao WHERE id_filial=%s AND status='Aguardando Exame'", (id_filial,), fetch=True)[0][0]
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Alunos Ativos", qtd)
        c2.metric("Treinos Hoje", treinos_hoje)
        c3.metric("Turmas", qtd_turmas)
        
        label_pend = "✅ Tudo OK"
        val_pend = "0"
        if pend_adm > 0: 
            label_pend = "⚠️ Pend. Financeira"
            val_pend = f"{pend_adm}"
        elif pend_exame > 0:
            label_pend = "🥋 Exames a Fazer"
            val_pend = f"{pend_exame}"
        c4.metric(label_pend, val_pend)

        st.write("") 
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            with st.container(border=True):
                st.subheader("🎂 Aniversariantes do Mês")
                q_niver = "SELECT nome_completo, to_char(data_nascimento, 'DD/MM') as dia FROM usuarios WHERE id_filial=%s AND EXTRACT(MONTH FROM data_nascimento) = EXTRACT(MONTH FROM CURRENT_DATE) ORDER BY dia"
                nivers = executar_query(q_niver, (id_filial,), fetch=True)
                if nivers:
                    for n in nivers: st.markdown(f"🎉 **{n['dia']}** - {n['Nome']}")
                else: st.caption("Nenhum.")
            
            with st.container(border=True):
                st.subheader("⚡ Acesso Rápido")
                bt1, bt2 = st.columns(2)
                if bt1.button("Fazer Chamada", use_container_width=True): st.toast("Vá para a aba Chamada ➜")
                if bt2.button("Matricular", use_container_width=True): st.toast("Vá para a aba Equipe > Novo ➜")

        with col_right:
            with st.container(border=True):
                st.subheader("📊 Faixas da Filial")
                res_faixa = executar_query("SELECT faixa, COUNT(*) as qtd FROM usuarios WHERE id_filial=%s AND perfil='aluno' AND status_conta='Ativo' GROUP BY faixa", (id_filial,), fetch=True)
                if res_faixa:
                    df_pizza = pd.DataFrame(res_faixa, columns=['Faixa', 'Qtd'])
                    fig_p = px.pie(df_pizza, values='Qtd', names='Faixa', hole=0.4)
                    st.plotly_chart(fig_p, use_container_width=True)

    with tab_chamada:
        c1, c2 = st.columns([1, 2])
        data_aula = c1.date_input("Data", date.today())
        turmas = executar_query("SELECT id, nome FROM turmas WHERE id_filial=%s", (id_filial,), fetch=True)
        d_turmas = {t['nome']: t['id'] for t in turmas} if turmas else {}
        sel_turma = c2.selectbox("Turma", list(d_turmas.keys())) if d_turmas else None
        if sel_turma:
            id_t = d_turmas[sel_turma]
            ja_veio = [x[0] for x in executar_query("SELECT id_aluno FROM checkins WHERE id_turma=%s AND data_aula=%s", (id_t, data_aula), fetch=True)]
            alunos = executar_query("SELECT id, nome_completo, faixa FROM usuarios WHERE id_turma=%s AND status_conta='Ativo' ORDER BY nome_completo", (id_t,), fetch=True)
            with st.form("ch"):
                checks = []
                for a in alunos:
                    if st.checkbox(f"{a['nome_completo']} ({a['faixa']})", value=(a['id'] in ja_veio), key=f"c_{a['id']}"): checks.append(a['id'])
                if st.form_submit_button("Salvar Chamada"):
                    executar_query("DELETE FROM checkins WHERE id_turma=%s AND data_aula=%s", (id_t, data_aula))
                    for uid in checks: executar_query("INSERT INTO checkins (id_aluno, id_turma, id_filial, data_aula) VALUES (%s, %s, %s, %s)", (uid, id_t, id_filial, data_aula))
                    st.success("Salvo!"); time.sleep(0.5); st.rerun()

    with tab_graduacao:
        st.subheader("Gestão de Faixas")
        if eh_admin:
            pendentes = executar_query("SELECT s.id, u.nome_completo, s.nova_faixa FROM solicitacoes_graduacao s JOIN usuarios u ON s.id_aluno=u.id WHERE s.id_filial=%s AND s.status='Pendente'", (id_filial,), fetch=True)
            if pendentes:
                with st.container(border=True):
                    st.markdown("#### 👮‍♂️ Autorização Financeira")
                    for p in pendentes:
                        c1, c2 = st.columns([3, 1])
                        c1.write(f"**{p['nome_completo']}** ➝ {p['nova_faixa']}")
                        if c2.button("Autorizar 💲", key=f"aut_{p['id']}"):
                            executar_query("UPDATE solicitacoes_graduacao SET status='Aguardando Exame' WHERE id=%s", (p['id'],))
                            st.rerun()

        aguardando = executar_query("SELECT s.id, u.nome_completo, s.nova_faixa FROM solicitacoes_graduacao s JOIN usuarios u ON s.id_aluno=u.id WHERE s.id_filial=%s AND s.status='Aguardando Exame'", (id_filial,), fetch=True)
        if aguardando:
            with st.container(border=True):
                st.markdown("#### 🥋 Registrar Resultado do Exame")
                for e in aguardando:
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"**{e['nome_completo']}** (Exame: {e['nova_faixa']})")
                    if c2.button("Aprovado ✅", key=f"ex_{e['id']}"):
                        executar_query("UPDATE solicitacoes_graduacao SET status='Aguardando Homologacao' WHERE id=%s", (e['id'],))
                        st.toast("Enviado ao Líder!"); time.sleep(1); st.rerun()

        st.markdown("#### 📡 Radar de Alunos")
        alunos = executar_query("SELECT id, nome_completo, faixa, graus, data_nascimento, data_ultimo_grau, data_inicio FROM usuarios WHERE id_filial=%s AND perfil='aluno' AND status_conta='Ativo' ORDER BY nome_completo", (id_filial,), fetch=True)
        if alunos:
            for a in alunos:
                marco = a['data_ultimo_grau'] or a['data_inicio'] or date.today()
                pres = executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s AND data_aula >= %s", (a['id'], marco), fetch=True)[0][0]
                pronto, msg, prog, troca = calcular_status_graduacao(a, pres)
                
                with st.expander(f"{'🔥' if pronto else '⏳'} {a['nome_completo']} - {msg}"):
                    st.progress(prog)
                    c1, c2 = st.columns(2)
                    if c1.button("+1 Grau", key=f"g_{a['id']}"):
                        executar_query("UPDATE usuarios SET graus = graus + 1, data_ultimo_grau = CURRENT_DATE WHERE id=%s", (a['id'],))
                        st.toast("Grau +1"); time.sleep(1); st.rerun()
                    if troca:
                        nf = get_proxima_faixa(a['faixa'])
                        status = executar_query("SELECT status FROM solicitacoes_graduacao WHERE id_aluno=%s AND status != 'Concluido'", (a['id'],), fetch=True)
                        if status: st.info(f"Em andamento: {status[0][0]}")
                        else:
                            if c2.button(f"INDICAR {nf} 🔼", key=f"ind_{a['id']}"):
                                executar_query("INSERT INTO solicitacoes_graduacao (id_aluno, id_filial, faixa_atual, nova_faixa, status) VALUES (%s, %s, %s, %s, 'Pendente')", (a['id'], id_filial, a['faixa'], nf))
                                st.success("Indicado!"); time.sleep(1); st.rerun()

    with tab_turmas:
        c_novo, c_lista = st.columns([1, 2])
        with c_novo:
            with st.form("ft"):
                nm = st.text_input("Nome")
                ds = st.text_input("Dias")
                hr = st.text_input("Horário")
                if st.form_submit_button("Criar"):
                    executar_query("INSERT INTO turmas (nome, dias, horario, responsavel, id_filial) VALUES (%s, %s, %s, '', %s)", (nm, ds, hr, id_filial))
                    st.rerun()
        with c_lista:
            st.dataframe(pd.DataFrame(executar_query("SELECT nome, dias, horario FROM turmas WHERE id_filial=%s", (id_filial,), fetch=True), columns=['Turma', 'Dias', 'Horario']), use_container_width=True)

    with tab_alunos:
        tab_lista, tab_novo = st.tabs(["📋 Gestão", "➕ Novo"])
        if st.session_state.aluno_editando:
            aid = st.session_state.aluno_editando
            dados = executar_query("SELECT * FROM usuarios WHERE id=%s", (aid,), fetch=True)[0]
            st.info(f"Editando: {dados['nome_completo']}")
            with st.form("edit"):
                nome = st.text_input("Nome", value=dados['nome_completo'])
                p_atual = dados['perfil']
                p_novo = st.selectbox("Cargo", list(CARGOS.keys()), index=list(CARGOS.keys()).index(p_atual)) if eh_admin else p_atual
                if st.form_submit_button("Salvar"):
                    executar_query("UPDATE usuarios SET nome_completo=%s, perfil=%s WHERE id=%s", (nome, p_novo, aid))
                    st.session_state.aluno_editando = None; st.rerun()
                if st.form_submit_button("Cancelar"):
                    st.session_state.aluno_editando = None; st.rerun()
        else:
            with tab_lista:
                membros = executar_query("SELECT id, nome_completo, faixa, perfil, email FROM usuarios WHERE id_filial=%s AND status_conta='Ativo' ORDER BY nome_completo", (id_filial,), fetch=True)
                if membros:
                    for m in membros:
                        c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                        c1.write(m['nome_completo'])
                        c2.caption(CARGOS.get(m['perfil'], 'Aluno'))
                        c3.write(m['faixa'])
                        col_ed, col_del = c4.columns(2)
                        if col_ed.button("✏️", key=f"e_{m['id']}"): st.session_state.aluno_editando = m['id']; st.rerun()
                        if eh_admin and m['email'] != user['email']:
                            if col_del.button("🗑️", key=f"d_{m['id']}"):
                                executar_query("UPDATE usuarios SET status_conta='Inativo' WHERE id=%s", (m['id'],))
                                st.rerun()
        with tab_novo:
            with st.form("novo"):
                nm = st.text_input("Nome")
                em = st.text_input("Email")
                nas = st.date_input("Nascimento", date(2000,1,1), min_value=date(1920,1,1), max_value=date.today())
                if st.form_submit_button("Cadastrar"):
                    executar_query("INSERT INTO usuarios (nome_completo, email, senha, data_nascimento, id_filial, perfil, status_conta, faixa, graus) VALUES (%s, %s, '123', %s, %s, 'aluno', 'Ativo', 'Branca', 0)", (nm, em, nas, id_filial))
                    st.success("Cadastrado!"); time.sleep(1); st.rerun()

# ==================================================
# 5. ROUTER
# ==================================================
if not st.session_state.logado:
    tela_login()
else:
    p = st.session_state.usuario['perfil']
    if p == 'lider': painel_lider()
    elif p == 'monitor': painel_monitor()
    else: painel_adm_filial()