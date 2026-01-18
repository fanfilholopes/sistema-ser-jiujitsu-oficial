from datetime import date, timedelta
import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
import time
import requests

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="SER Official", page_icon="🥋", layout="wide")

# --- ESTADO DA SESSÃO ---
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'usuario' not in st.session_state:
    st.session_state.usuario = None 
if 'endereco_temp' not in st.session_state:
    st.session_state.endereco_temp = {"rua": "", "bairro": "", "cidade": "", "uf": ""}

# --- CONEXÃO ---
@st.cache_resource
def get_connection():
    try:
        return psycopg2.connect(
            host=st.secrets["postgres"]["host"],
            database=st.secrets["postgres"]["database"],
            user=st.secrets["postgres"]["user"],
            password=st.secrets["postgres"]["password"],
            port=st.secrets["postgres"]["port"]
        )
    except Exception as e:
        st.error(f"Erro Conexão: {e}")
        return None

def executar_query(query, params=None, fetch=False):
    conn = get_connection()
    if not conn: return None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(query, params)
            if fetch: return cur.fetchall()
            else: conn.commit(); return True
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return "ERRO_DUPLICADO"
    except Exception as e:
        conn.rollback()
        st.error(f"Erro SQL: {e}")
        return None

def buscar_dados_cep(cep):
    cep = cep.replace("-", "").replace(".", "").strip()
    if len(cep) == 8:
        try:
            response = requests.get(f"https://viacep.com.br/ws/{cep}/json/")
            if response.status_code == 200:
                dados = response.json()
                if "erro" not in dados:
                    return dados
        except:
            pass
    return None

# --- ORDEM DAS FAIXAS (NOVO: Para promoção automática) ---
ORDEM_FAIXAS = ["Branca", "Cinza", "Amarela", "Laranja", "Verde", "Azul", "Roxa", "Marrom", "Preta"]

def get_proxima_faixa(faixa_atual):
    try:
        idx = ORDEM_FAIXAS.index(faixa_atual)
        if idx + 1 < len(ORDEM_FAIXAS):
            return ORDEM_FAIXAS[idx + 1]
    except:
        pass
    return faixa_atual # Se não achar ou for Preta, mantém

# --- LÓGICA DE GRADUAÇÃO (CÉREBRO ATUALIZADO) ---
def calcular_status_graduacao(aluno, presencas):
    hoje = date.today()
    nasc = aluno['data_nascimento']
    ultimo_grau = aluno['data_ultimo_grau']
    faixa = aluno['faixa']
    graus_atuais = aluno['graus'] or 0
    
    if not ultimo_grau: ultimo_grau = hoje

    # Cálculo da Idade
    idade = (hoje - nasc).days // 365
    is_kid = idade < 16 

    # --- REGRA 1: KIDS (4 a 15 anos) ---
    # Critério: Frequência (8 aulas = 1 grau/mês)
    if is_kid:
        meta_aulas = 8
        progresso = min(presencas / meta_aulas, 1.0)
        pronto = presencas >= meta_aulas
        
        if pronto: 
            msg = f"✅ Completou {presencas} aulas (Meta: 8)"
        else: 
            msg = f"Treinando: {presencas}/8 aulas"
            
        # Kids por enquanto apenas ganham graus nesta lógica simplificada
        return pronto, msg, progresso, False 

    # --- REGRA 2: FAIXA PRETA (IBJJF) ---
    elif faixa == 'Preta':
        regras_preta = {0: 3, 1: 3, 2: 3, 3: 5, 4: 5, 5: 5, 6: 7, 7: 7, 8: 10}
        anos_necessarios = regras_preta.get(graus_atuais, 99)
        data_meta = ultimo_grau + timedelta(days=anos_necessarios*365)
        
        pronto = hoje >= data_meta
        dias_passados = (hoje - ultimo_grau).days
        dias_meta = anos_necessarios * 365
        progresso = min(dias_passados / dias_meta, 1.0) if dias_meta > 0 else 0
        
        if pronto: msg = f"✅ Cumpriu {anos_necessarios} anos de faixa."
        else: msg = f"Aguardando tempo ({anos_necessarios} anos). Meta: {data_meta.strftime('%d/%m/%Y')}"
            
        return pronto, msg, progresso, False

    # --- REGRA 3: ADULTOS (Branca a Marrom) ---
    # Critério: 4 Graus = Troca de Faixa. Menos de 4 = Novo Grau. (6 Meses de carência)
    else:
        meses_necessarios = 6
        dias_necessarios = 180 
        data_meta = ultimo_grau + timedelta(days=dias_necessarios)
        
        pronto = hoje >= data_meta
        dias_passados = (hoje - ultimo_grau).days
        progresso = min(dias_passados / dias_necessarios, 1.0)
        
        # Lógica de Troca de Faixa
        troca_de_faixa = False
        if graus_atuais >= 4:
            troca_de_faixa = True
            prox_faixa = get_proxima_faixa(faixa)
            acao_texto = f"Mudar para Faixa {prox_faixa}"
        else:
            acao_texto = "Próximo Grau"

        if pronto:
            msg = f"✅ Apto para: {acao_texto} (Cumpriu carência)"
        else:
            msg = f"Carência: Falta {(dias_necessarios - dias_passados)//30} meses para {acao_texto}."
            
        # Retorna 4 valores agora!
        return pronto, msg, progresso, troca_de_faixa

# ==========================================
# 1. TELA DE LOGIN
# ==========================================
def tela_login():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        try: st.image("logoser.jpg", width=200)
        except: pass
        st.title("🥋 Equipe SER - Acesso Oficial")
        with st.form("login_form"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            entrar = st.form_submit_button("Acessar Sistema", use_container_width=True)
            if entrar:
                usuario = executar_query("SELECT id, nome_completo, perfil, id_filial, status_conta FROM usuarios WHERE email = %s AND senha = %s", (email, senha), fetch=True)
                if usuario:
                    dados = usuario[0]
                    if dados['status_conta'] == 'Ativo':
                        st.session_state.logado = True
                        st.session_state.usuario = dict(dados)
                        st.success(f"Bem-vindo, {dados['nome_completo']}!")
                        time.sleep(1)
                        st.rerun()
                    else: st.warning("🔒 Conta Inativa.")
                else: st.error("🚫 Dados incorretos.")

# ==========================================
# 2. PAINÉIS
# ==========================================
def painel_lider():
    try: st.sidebar.image("logoser.jpg", width=150)
    except: st.sidebar.image("https://img.icons8.com/color/96/karate.png", width=100)
    st.sidebar.title("Painel Mestre 👑")
    nome_logado = st.session_state.usuario['nome_completo']
    st.sidebar.info(f"Logado como: {nome_logado}")
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()
        
    st.title("🌍 QG da Equipe SER")
    tab_dash, tab_gestao_filiais, tab_usuarios = st.tabs(["📊 Visão Geral", "🏢 Gestão de Filiais", "👥 Diretório Global"])
    
    with tab_dash:
        res_filiais = executar_query("SELECT COUNT(*) FROM filiais", fetch=True)
        res_usuarios = executar_query("SELECT COUNT(*) FROM usuarios", fetch=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Filiais", res_filiais[0][0] if res_filiais else 0)
        c2.metric("Membros", res_usuarios[0][0] if res_usuarios else 0)
        c3.metric("Faturamento", "R$ 0,00", "Em breve")

    with tab_gestao_filiais:
        st.subheader("Unidades da Rede")
        q_lista = "SELECT f.id, f.nome, f.responsavel_nome, f.telefone_contato, f.cidade, f.bairro, f.endereco, f.numero, f.estado FROM filiais f ORDER BY f.id"
        df = pd.DataFrame(executar_query(q_lista, fetch=True), columns=['ID', 'Filial', 'Responsável', 'Tel', 'Cidade', 'Bairro', 'Rua', 'Nº', 'UF'])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.divider()
        with st.expander("➕ Cadastrar Nova Filial"):
            c_cep, c_btn = st.columns([3, 1])
            cep = c_cep.text_input("CEP", max_chars=9)
            if c_btn.button("🔍"):
                d = buscar_dados_cep(cep)
                if d: 
                    st.session_state.endereco_temp = {"rua": d['logradouro'], "bairro": d['bairro'], "cidade": d['localidade'], "uf": d['uf']}
                    st.success("Achamos!")
                else: st.error("Não achamos.")
            
            with st.form("nova_filial", clear_on_submit=True):
                nome = st.text_input("Nome Filial")
                val = st.session_state.endereco_temp
                c1, c2 = st.columns([3, 1])
                rua = c1.text_input("Rua", value=val['rua'])
                num = c2.text_input("Número")
                c3, c4, c5 = st.columns([2, 2, 1])
                bairro = c3.text_input("Bairro", value=val['bairro'])
                cid = c4.text_input("Cidade", value=val['cidade'])
                uf = c5.text_input("UF", value=val['uf'])
                st.markdown("---")
                c6, c7 = st.columns(2)
                adm = c6.text_input("Nome Adm")
                zap = c7.text_input("Zap")
                email = c6.text_input("Email")
                senha = c7.text_input("Senha", type="password")
                
                if st.form_submit_button("Inaugurar"):
                    res = executar_query("INSERT INTO filiais (nome, endereco, numero, bairro, cidade, estado, cep, responsavel_nome, telefone_contato) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id", (nome, rua, num, bairro, cid, uf, cep, adm, zap), fetch=True)
                    if res:
                        nid = res[0][0]
                        executar_query("INSERT INTO usuarios (nome_completo, email, senha, telefone, perfil, id_filial, status_conta) VALUES (%s, %s, %s, %s, 'adm_filial', %s, 'Ativo')", (adm, email, senha, zap, nid))
                        st.toast("Sucesso!"); time.sleep(1); st.rerun()

    with tab_usuarios:
        df = pd.DataFrame(executar_query("SELECT u.nome_completo, u.perfil, u.email, f.nome, u.status_conta FROM usuarios u LEFT JOIN filiais f ON u.id_filial = f.id ORDER BY u.id DESC", fetch=True), columns=['Nome', 'Perfil', 'Email', 'Filial', 'Status'])
        st.dataframe(df, use_container_width=True)

def painel_adm_filial():
    user = st.session_state.usuario
    id_filial = user['id_filial']
    dados_filial = executar_query("SELECT nome FROM filiais WHERE id = %s", (id_filial,), fetch=True)
    nome_filial = dados_filial[0]['nome']
    
    try: st.sidebar.image("logoser.jpg", width=150)
    except: st.sidebar.image("https://img.icons8.com/color/96/kimono.png", width=100)
    st.sidebar.title(f"{nome_filial}")
    st.sidebar.caption(f"Gerente: {user['nome_completo']}")
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()

    st.title(f"Painel de Gestão - {nome_filial}")
    
    tab_dash, tab_chamada, tab_graduacao, tab_turmas, tab_alunos = st.tabs(["📊 Visão Geral", "✅ Chamada", "🎓 Graduações", "📅 Turmas", "👥 Alunos"])
    
    with tab_dash:
        q_turmas = executar_query("SELECT COUNT(*) FROM turmas WHERE id_filial = %s", (id_filial,), fetch=True)
        q_alunos = executar_query("SELECT COUNT(*) FROM usuarios WHERE perfil = 'aluno' AND id_filial = %s", (id_filial,), fetch=True)
        q_hoje = executar_query("SELECT COUNT(*) FROM checkins WHERE id_filial = %s AND data_aula = CURRENT_DATE", (id_filial,), fetch=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Alunos", q_alunos[0][0] if q_alunos else 0)
        c2.metric("Treinos Hoje", q_hoje[0][0] if q_hoje else 0)
        c3.metric("Turmas", q_turmas[0][0] if q_turmas else 0)

    # --- ABA CHAMADA ---
    with tab_chamada:
        st.subheader("Registrar Presença")
        turmas = executar_query("SELECT id, nome FROM turmas WHERE id_filial = %s", (id_filial,), fetch=True)
        d_turmas = {t['nome']: t['id'] for t in turmas} if turmas else {}
        
        if d_turmas:
            c_data, c_turma = st.columns([1, 2])
            data_aula = c_data.date_input("Data da Aula", value=date.today(), max_value=date.today())
            sel_turma = c_turma.selectbox("Turma", list(d_turmas.keys()))
            
            id_sel = d_turmas[sel_turma]
            
            alunos = executar_query("SELECT id, nome_completo, faixa, graus FROM usuarios WHERE id_turma = %s AND status_conta = 'Ativo' ORDER BY nome_completo", (id_sel,), fetch=True)
            
            q_ja_veio = "SELECT id_aluno FROM checkins WHERE id_turma = %s AND data_aula = %s"
            ja_veio_raw = executar_query(q_ja_veio, (id_sel, data_aula), fetch=True)
            lista_presentes = [x[0] for x in ja_veio_raw] if ja_veio_raw else []

            if alunos:
                with st.form("chamada"):
                    st.markdown(f"**Lista de Chamada** - {data_aula.strftime('%d/%m/%Y')}")
                    presencas_marcadas = []
                    
                    for a in alunos:
                        is_present = a['id'] in lista_presentes
                        label = f"{a['nome_completo']} ({a['faixa']} - {a['graus']}º)"
                        if is_present: label += " ✅"
                        
                        if st.checkbox(label, value=is_present, key=f"c_{a['id']}_{data_aula}"):
                            presencas_marcadas.append(a['id'])
                            
                    if st.form_submit_button("💾 Salvar Chamada"):
                        to_add = [p for p in presencas_marcadas if p not in lista_presentes]
                        to_remove = [p for p in lista_presentes if p not in presencas_marcadas]
                        
                        for pid in to_add:
                            executar_query("INSERT INTO checkins (id_aluno, id_turma, id_filial, data_aula) VALUES (%s, %s, %s, %s)", (pid, id_sel, id_filial, data_aula))
                        for pid in to_remove:
                            executar_query("DELETE FROM checkins WHERE id_aluno = %s AND id_turma = %s AND data_aula = %s", (pid, id_sel, data_aula))
                            
                        st.success(f"Chamada do dia {data_aula.strftime('%d/%m/%Y')} atualizada!")
                        time.sleep(1)
                        st.rerun()
            else: st.info("Turma vazia.")
        else: st.warning("Crie turmas antes.")

    # --- ABA GRADUAÇÃO ---
    with tab_graduacao:
        st.subheader("Radar de Promoção 🥋")
        with st.expander("ℹ️ Ver Regras da Equipe (Cola do Professor)"):
            st.markdown("""
            **1. Kids (4-15 anos):** 8 Aulas = 1 Grau.
            **2. Adultos (Branca a Marrom):** 6 Meses de carência.
               * Se tiver 4 graus -> Muda de Faixa.
               * Se tiver < 4 graus -> Ganha Grau.
            **3. Faixa Preta (Regra IBJJF):** Anos de estrada.
            """)
        
        q_radar = """SELECT id, nome_completo, faixa, graus, data_nascimento, data_ultimo_grau, id_turma FROM usuarios WHERE id_filial = %s AND perfil = 'aluno' AND status_conta = 'Ativo' ORDER BY nome_completo"""
        alunos_radar = executar_query(q_radar, (id_filial,), fetch=True)
        contador_prontos = 0
        
        if alunos_radar:
            for aluno in alunos_radar:
                ultimo_grau = aluno['data_ultimo_grau'] or date.today()
                q_pres = "SELECT COUNT(*) FROM checkins WHERE id_aluno = %s AND data_aula >= %s"
                res_pres = executar_query(q_pres, (aluno['id'], ultimo_grau), fetch=True)
                total_presencas = res_pres[0][0] if res_pres else 0
                
                pronto, msg_meta, progresso, troca_faixa = calcular_status_graduacao(aluno, total_presencas)
                
                if pronto:
                    contador_prontos += 1
                    with st.container(border=True):
                        c_info, c_btn = st.columns([3, 1])
                        with c_info:
                            st.markdown(f"### 🔥 **{aluno['nome_completo']}**")
                            st.caption(f"Atual: {aluno['faixa']} ({aluno['graus']}º Grau) | Desde: {ultimo_grau.strftime('%d/%m/%Y')}")
                            st.markdown(f"**Status:** {msg_meta}")
                            st.progress(progresso)
                        with c_btn:
                            st.write("") 
                            
                            texto_botao = "Promover (+1 Grau)"
                            if troca_faixa and aluno['perfil'] != 'Preta': 
                                texto_botao = "Graduar Faixa 🔼"

                            if st.button(texto_botao, key=f"prom_{aluno['id']}"):
                                if troca_faixa:
                                    nova_faixa = get_proxima_faixa(aluno['faixa'])
                                    q_up = "UPDATE usuarios SET faixa = %s, graus = 0, data_graduacao = CURRENT_DATE, data_ultimo_grau = CURRENT_DATE WHERE id = %s"
                                    executar_query(q_up, (nova_faixa, aluno['id']))
                                    st.balloons(); st.toast(f"Parabéns! Nova Faixa: {nova_faixa}!"); time.sleep(2); st.rerun()
                                else:
                                    novos_graus = (aluno['graus'] or 0) + 1
                                    q_up = "UPDATE usuarios SET graus = %s, data_ultimo_grau = CURRENT_DATE WHERE id = %s"
                                    executar_query(q_up, (novos_graus, aluno['id']))
                                    st.balloons(); st.toast(f"Grau adicionado!"); time.sleep(2); st.rerun()
            
            if contador_prontos == 0: st.success("Tudo em dia! Ninguém pendente de graduação.")
        else: st.info("Sem alunos ativos.")

    with tab_turmas:
        c1, c2 = st.columns([1, 2])
        with c1:
            with st.form("nt"):
                n = st.text_input("Nome da Turma"); d = st.text_input("Dias"); h = st.text_input("Horário")
                if st.form_submit_button("Salvar"):
                    executar_query("INSERT INTO turmas (nome, dias, horario, id_filial) VALUES (%s, %s, %s, %s)", (n, d, h, id_filial))
                    st.rerun()
        with c2:
            df = pd.DataFrame(executar_query("SELECT nome, dias, horario FROM turmas WHERE id_filial = %s ORDER BY nome", (id_filial,), fetch=True), columns=['Turma', 'Dias', 'Horário'])
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_alunos:
        turmas = executar_query("SELECT id, nome FROM turmas WHERE id_filial = %s", (id_filial,), fetch=True)
        dt = {t['nome']: t['id'] for t in turmas} if turmas else {}
        
        with st.expander("➕ Matricular Novo Aluno", expanded=True):
            if dt:
                # --- DADOS FORA DO FORM (Para atualizar a tela) ---
                c_dtn, c_av = st.columns([1, 2])
                dn = c_dtn.date_input("Nascimento", value=date(2015,1,1), min_value=date(1940,1,1), max_value=date.today(), format="DD/MM/YYYY")
                
                # Cálculo da idade
                id_calc = (date.today() - dn).days // 365
                is_kid = id_calc < 16 
                
                if is_kid: c_av.warning(f"👶 Aluno Kids ({id_calc} anos). Campos do Responsável liberados.")
                else: c_av.success(f"🧑 Adulto/Juvenil ({id_calc} anos).")
                
                c_fx, c_gr = st.columns(2)
                fx = c_fx.selectbox("Faixa", ["Branca", "Cinza", "Amarela", "Laranja", "Verde", "Azul", "Roxa", "Marrom", "Preta"])
                gr = c_gr.selectbox("Graus", [0,1,2,3,4])
                
                c_dfx, c_dgr = st.columns(2)
                dfx = c_dfx.date_input("Data Faixa", value=date.today(), format="DD/MM/YYYY")
                
                # AQUI ESTÁ A CORREÇÃO: Mostra aviso se for 0, mostra Input se for > 0
                if gr == 0:
                    dgr = dfx
                    c_dgr.info("ℹ️ Sem graus: O tempo conta da Data da Faixa.")
                else:
                    dgr = c_dgr.date_input("Data Último Grau", value=date.today(), format="DD/MM/YYYY")

                # --- DADOS DENTRO DO FORM ---
                with st.form("naluno", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    nm = c1.text_input("Nome do Aluno")
                    em = c2.text_input("Email (Login)")
                    c3, c4 = st.columns(2)
                    zp = c3.text_input("WhatsApp do Aluno")
                    tr = c4.selectbox("Turma", list(dt.keys()))
                    
                    nr, trp = None, None
                    if is_kid:
                        st.markdown("---")
                        st.markdown("##### 👨‍👩‍👧 Dados do Responsável")
                        c5, c6 = st.columns(2)
                        nr = c5.text_input("Nome do Responsável")
                        trp = c6.text_input("WhatsApp do Responsável")
                    
                    st.markdown("---")
                    if st.form_submit_button("✅ Matricular Aluno"):
                        q = """INSERT INTO usuarios (nome_completo, email, senha, telefone, data_nascimento, faixa, graus, id_filial, id_turma, perfil, status_conta, nome_responsavel, telefone_responsavel, data_graduacao, data_ultimo_grau) VALUES (%s, %s, 'mudar123', %s, %s, %s, %s, %s, %s, 'aluno', 'Ativo', %s, %s, %s, %s)"""
                        res = executar_query(q, (nm, em, zp, dn, fx, gr, id_filial, dt[tr], nr, trp, dfx, dgr))
                        if res == "ERRO_DUPLICADO": st.error("Email já existe")
                        else: st.toast("Sucesso!"); time.sleep(1); st.rerun()
            else: st.warning("⚠️ Crie turmas antes de matricular.")
            
        st.divider()
        df = pd.DataFrame(executar_query("SELECT nome_completo, faixa, graus, telefone FROM usuarios WHERE id_filial = %s AND perfil = 'aluno'", (id_filial,), fetch=True), columns=['Nome', 'Faixa', 'Graus', 'Zap'])
        st.dataframe(df, use_container_width=True, hide_index=True)

if not st.session_state.logado: tela_login()
else:
    if st.session_state.usuario['perfil'] == 'lider': painel_lider()
    elif st.session_state.usuario['perfil'] == 'adm_filial': painel_adm_filial()
    else: st.warning("Acesso restrito."); st.button("Sair", on_click=lambda: st.session_state.update(logado=False))