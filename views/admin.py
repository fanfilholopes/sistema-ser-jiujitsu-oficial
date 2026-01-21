import streamlit as st
import database as db
import utils
import pandas as pd
import plotly.express as px
from datetime import date

def painel_adm_filial():
    user = st.session_state.usuario
    id_filial = user['id_filial']
    perfil = user['perfil']
    eh_admin = perfil == 'adm_filial'
    
    # Sidebar
    nome_filial = db.executar_query("SELECT nome FROM filiais WHERE id=%s", (id_filial,), fetch=True)
    nome_f = nome_filial[0]['nome'] if nome_filial else "Filial"
    
    try: st.sidebar.image("logoser.jpg", width=150)
    except: pass
    st.sidebar.markdown(f"## {nome_f}")
    st.sidebar.caption(f"{utils.CARGOS.get(perfil, perfil).upper()}")
    st.sidebar.markdown("---")
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()

    tab_dash, tab_chamada, tab_grad, tab_turmas, tab_alunos = st.tabs(["📊 Painel", "✅ Chamada", "🎓 Graduações", "📅 Turmas", "👥 Equipe"])

    # 1. DASHBOARD
    with tab_dash:
        aviso = db.executar_query("SELECT mensagem FROM avisos WHERE ativo=TRUE ORDER BY id DESC LIMIT 1", fetch=True)
        if aviso: st.markdown(f"""<div class="aviso-box">📢 {aviso[0]['mensagem']}</div>""", unsafe_allow_html=True)

        qtd = db.executar_query("SELECT COUNT(*) FROM usuarios WHERE id_filial=%s AND status_conta='Ativo' AND perfil='aluno'", (id_filial,), fetch=True)[0][0]
        treinos = db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_filial=%s AND data_aula=CURRENT_DATE", (id_filial,), fetch=True)[0][0]
        c1, c2 = st.columns(2)
        c1.metric("Alunos", qtd)
        c2.metric("Treinos Hoje", treinos)
        
        res_faixa = db.executar_query("SELECT faixa, COUNT(*) as qtd FROM usuarios WHERE id_filial=%s AND perfil='aluno' AND status_conta='Ativo' GROUP BY faixa", (id_filial,), fetch=True)
        if res_faixa:
            st.plotly_chart(px.pie(pd.DataFrame(res_faixa, columns=['Faixa', 'Qtd']), values='Qtd', names='Faixa', hole=0.4), use_container_width=True)

    # 2. CHAMADA
    with tab_chamada:
        turmas = db.executar_query("SELECT id, nome FROM turmas WHERE id_filial=%s", (id_filial,), fetch=True)
        d_t = {t['nome']: t['id'] for t in turmas} if turmas else {}
        sel = st.selectbox("Turma", list(d_t.keys())) if d_t else None
        if sel:
            id_t = d_t[sel]
            als = db.executar_query("SELECT id, nome_completo FROM usuarios WHERE id_turma=%s AND status_conta='Ativo'", (id_t,), fetch=True)
            with st.form("ch"):
                checks = []
                for a in als:
                    if st.checkbox(a['nome_completo'], key=f"c_{a['id']}"): checks.append(a['id'])
                if st.form_submit_button("Salvar"):
                    db.executar_query("DELETE FROM checkins WHERE id_turma=%s AND data_aula=CURRENT_DATE", (id_t,))
                    for uid in checks: db.executar_query("INSERT INTO checkins (id_aluno, id_turma, id_filial, data_aula) VALUES (%s, %s, %s, CURRENT_DATE)", (uid, id_t, id_filial))
                    st.success("Salvo!"); st.rerun()

    # 3. GRADUAÇÃO
    with tab_grad:
        if eh_admin:
            pend = db.executar_query("SELECT s.id, u.nome_completo, s.nova_faixa FROM solicitacoes_graduacao s JOIN usuarios u ON s.id_aluno=u.id WHERE s.id_filial=%s AND s.status='Pendente'", (id_filial,), fetch=True)
            if pend:
                st.write("**Financeiro:**")
                for p in pend:
                    c1, c2 = st.columns([3,1])
                    c1.write(f"{p['nome_completo']} -> {p['nova_faixa']}")
                    if c2.button("Autorizar", key=f"au_{p['id']}"):
                        db.executar_query("UPDATE solicitacoes_graduacao SET status='Aguardando Exame' WHERE id=%s", (p['id'],))
                        st.rerun()
        
        exams = db.executar_query("SELECT s.id, u.nome_completo, s.nova_faixa FROM solicitacoes_graduacao s JOIN usuarios u ON s.id_aluno=u.id WHERE s.id_filial=%s AND s.status='Aguardando Exame'", (id_filial,), fetch=True)
        if exams:
            st.write("**Exame Prático:**")
            for e in exams:
                c1, c2 = st.columns([3,1])
                c1.write(f"{e['nome_completo']} -> {e['nova_faixa']}")
                if c2.button("Aprovado", key=f"ex_{e['id']}"):
                    db.executar_query("UPDATE solicitacoes_graduacao SET status='Aguardando Homologacao' WHERE id=%s", (e['id'],))
                    st.rerun()

        st.divider()
        st.markdown("#### 📡 Radar")
        alunos = db.executar_query("SELECT id, nome_completo, faixa, graus, data_nascimento, data_ultimo_grau, data_inicio FROM usuarios WHERE id_filial=%s AND perfil='aluno' AND status_conta='Ativo'", (id_filial,), fetch=True)
        if alunos:
            for a in alunos:
                marco = a['data_ultimo_grau'] or a['data_inicio'] or date.today()
                pres = db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s AND data_aula >= %s", (a['id'], marco), fetch=True)[0][0]
                _, msg, prog, troca = utils.calcular_status_graduacao(a, pres)
                with st.expander(f"{'🔥' if prog >=1 else '⏳'} {a['nome_completo']} - {msg}"):
                    st.progress(prog)
                    c1, c2 = st.columns(2)
                    if c1.button("+1 Grau", key=f"g_{a['id']}"):
                        db.executar_query("UPDATE usuarios SET graus = graus + 1, data_ultimo_grau = CURRENT_DATE WHERE id=%s", (a['id'],))
                        st.toast("Grau +1"); st.rerun()
                    if troca:
                        nf = utils.get_proxima_faixa(a['faixa'])
                        if c2.button(f"Indicar {nf}", key=f"ind_{a['id']}"):
                            db.executar_query("INSERT INTO solicitacoes_graduacao (id_aluno, id_filial, faixa_atual, nova_faixa, status) VALUES (%s, %s, %s, %s, 'Pendente')", (a['id'], id_filial, a['faixa'], nf))
                            st.success("Indicado!"); st.rerun()

    # 4. TURMAS
    with tab_turmas:
        with st.form("nt"):
            n = st.text_input("Nome")
            d = st.text_input("Dias")
            h = st.text_input("Horario")
            if st.form_submit_button("Criar"):
                db.executar_query("INSERT INTO turmas (nome, dias, horario, responsavel, id_filial) VALUES (%s, %s, %s, '', %s)", (n, d, h, id_filial))
                st.rerun()
        ts = db.executar_query("SELECT nome, dias, horario FROM turmas WHERE id_filial=%s", (id_filial,), fetch=True)
        if ts: st.dataframe(pd.DataFrame(ts), use_container_width=True)

    # 5. ALUNOS
    with tab_alunos:
        tab_l, tab_n = st.tabs(["Lista", "Novo"])
        with tab_l:
            membros = db.executar_query("SELECT id, nome_completo, faixa FROM usuarios WHERE id_filial=%s AND status_conta='Ativo'", (id_filial,), fetch=True)
            if membros:
                for m in membros:
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"{m['nome_completo']} ({m['faixa']})")
                    if eh_admin:
                        if c2.button("🗑️", key=f"d_{m['id']}"):
                            db.executar_query("UPDATE usuarios SET status_conta='Inativo' WHERE id=%s", (m['id'],))
                            st.rerun()
        with tab_n:
            # Cadastro Completo (Igual V34)
            turmas = db.executar_query("SELECT id, nome FROM turmas WHERE id_filial=%s", (id_filial,), fetch=True)
            opts_turma = {t['nome']: t['id'] for t in turmas} if turmas else {}
            
            st.subheader("Matricular Novo Aluno")
            c_data, c_aviso = st.columns([1, 2])
            nasc = c_data.date_input("Data de Nascimento", value=date(2015, 1, 1), min_value=date(1920, 1, 1), max_value=date.today())
            idade = (date.today() - nasc).days // 365
            is_kid = idade < 16
            
            if is_kid: c_aviso.warning(f"👶 KIDS ({idade} anos) - Resp. Obrigatório.")
            else: c_aviso.success(f"🥋 ADULTO ({idade} anos)")

            with st.form("form_aluno"):
                c1, c2 = st.columns([2, 1])
                nome = c1.text_input("Nome Completo")
                turma = c2.selectbox("Turma", list(opts_turma.keys())) if opts_turma else None
                c3, c4 = st.columns(2)
                faixa = c3.selectbox("Faixa", utils.ORDEM_FAIXAS)
                graus = c4.selectbox("Graus", [0,1,2,3,4])
                c5, c6 = st.columns(2)
                dt_inicio = c5.date_input("Início", date.today())
                dt_ult = c6.date_input("Último Grau", value=None)
                c7, c8 = st.columns(2)
                zap = c7.text_input("WhatsApp")
                email = c8.text_input("E-mail (Login)")
                
                nm_resp, tel_resp = None, None
                if is_kid:
                    st.divider(); st.markdown("### 👨‍👩‍👧 Responsável")
                    c_r1, c_r2 = st.columns(2)
                    nm_resp = c_r1.text_input("Nome Resp.")
                    tel_resp = c_r2.text_input("WhatsApp Resp.")

                if st.form_submit_button("Salvar"):
                    if not turma: st.error("Selecione turma.")
                    elif is_kid and not nm_resp: st.error("Responsável obrigatório.")
                    else:
                        ug = dt_ult if dt_ult else dt_inicio
                        res = db.executar_query(
                            """INSERT INTO usuarios (nome_completo, email, senha, telefone, data_nascimento, faixa, graus, id_filial, id_turma, perfil, status_conta, data_inicio, data_ultimo_grau, nome_responsavel, telefone_responsavel) 
                            VALUES (%s, %s, '123', %s, %s, %s, %s, %s, %s, 'aluno', 'Ativo', %s, %s, %s, %s)""",
                            (nome, email, zap, nasc, faixa, graus, id_filial, opts_turma[turma], dt_inicio, ug, nm_resp, tel_resp)
                        )
                        if res == "ERRO_DUPLICADO": st.error("Email já existe!")
                        elif res: st.success("Matriculado!"); st.rerun()