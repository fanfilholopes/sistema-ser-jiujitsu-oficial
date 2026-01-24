import streamlit as st
import database as db
import utils
import pandas as pd
from datetime import date
import time

def painel_aluno():
    user = st.session_state.usuario
    
    # --- CORES DAS FAIXAS (Local) ---
    CORES_FAIXAS = {
        'Branca': '#F0F0F0',
        'Cinza': '#A0A0A0',
        'Amarela': '#FFD700',
        'Laranja': '#FF8C00',
        'Verde': '#228B22',
        'Azul': '#0000FF',
        'Roxa': '#800080',
        'Marrom': '#8B4513',
        'Preta': '#000000'
    }

    # --- BUSCAR DADOS EXTRAS ---
    filial_data = db.executar_query("SELECT nome FROM filiais WHERE id=%s", (user['id_filial'],), fetch=True)
    nome_filial = filial_data[0]['nome'] if filial_data else "Matriz / Sede"

    nome_turma = "Não enturmado"
    detalhes_turma = ""
    if user['id_turma']:
        turma_data = db.executar_query("SELECT nome, dias, horario FROM turmas WHERE id=%s", (user['id_turma'],), fetch=True)
        if turma_data:
            t = turma_data[0]
            nome_turma = t['nome']
            detalhes_turma = f"{t['dias']} às {t['horario']}"

    # --- SIDEBAR ---
    try: st.sidebar.image("logoser.jpg", width=150)
    except: pass
    st.sidebar.markdown("## Área do Aluno")
    st.sidebar.caption(f"Olá, {user['nome_completo']}")
    
    st.sidebar.markdown(f"📍 **{nome_filial}**")
    st.sidebar.markdown(f"🥋 **{user['faixa']}** ({user['graus']}º Grau)")
    
    st.sidebar.markdown("---")
    if st.sidebar.button("Sair", key="sair_aluno"):
        st.session_state.logado = False
        st.rerun()

    # =======================================================
    # 1. CHECK-IN E GRADUAÇÃO
    # =======================================================
    checkin_hoje = db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s AND data_aula=CURRENT_DATE", (user['id'],), fetch=True)[0][0]
    
    solicitacao = db.executar_query("""
        SELECT nova_faixa, status FROM solicitacoes_graduacao 
        WHERE id_aluno=%s AND status != 'Concluido' 
        ORDER BY id DESC LIMIT 1
    """, (user['id'],), fetch=True)

    c_check, c_aviso_grad = st.columns([1, 2])

    with c_check:
        st.markdown("##### 📍 Presença Hoje")
        if checkin_hoje > 0:
            st.success("✅ Confirmada!")
        else:
            if st.button("📲 Fazer Check-in", type="primary", use_container_width=True):
                if user['id_turma']:
                    db.executar_query("""
                        INSERT INTO checkins (id_aluno, id_turma, id_filial, data_aula) 
                        VALUES (%s, %s, %s, CURRENT_DATE)
                    """, (user['id'], user['id_turma'], user['id_filial']))
                    st.toast("Check-in realizado com sucesso!")
                    time.sleep(1.5); st.rerun()
                else:
                    st.error("Você não está em uma turma. Fale com seu professor.")

    with c_aviso_grad:
        if solicitacao:
            sol = solicitacao[0]
            status_map = {
                'Pendente': '🟡 Aguardando Aprovação',
                'Aguardando Exame': '🥋 Aprovado! Prepare-se para o Exame.',
                'Aguardando Homologacao': '🎓 Exame Concluído! Aguardando Faixa.'
            }
            msg_status = status_map.get(sol['status'], sol['status'])
            st.info(f"🎉 **Parabéns!** Indicado para **{sol['nova_faixa']}**.\n\n**Status:** {msg_status}")

    st.divider()

    # =======================================================
    # 2. MURAL DE AVISOS
    # =======================================================
    avisos = db.executar_query("""
        SELECT titulo, mensagem, data_postagem FROM avisos 
        WHERE ativo=TRUE AND publico_alvo IN ('Todos', 'Alunos') 
        ORDER BY id DESC
    """, fetch=True)
    
    if avisos: 
        st.markdown("### 📢 Avisos")
        for av in avisos:
            with st.container(border=True):
                st.markdown(f"**{av['titulo']}** <small style='color:grey'>({av['data_postagem'].strftime('%d/%m')})</small>", unsafe_allow_html=True)
                st.write(av['mensagem'])
        st.divider()

    # =======================================================
    # 3. ESTATÍSTICAS E CARTEIRINHA
    # =======================================================
    c_card, c_stats = st.columns([1.2, 1.8])
    
    with c_card:
        cor_faixa = CORES_FAIXAS.get(user['faixa'], '#ccc')
        cor_texto_tag = 'black' if user['faixa'] in ['Branca', 'Amarela'] else 'white'

        # HTML SEM INDENTAÇÃO PARA NÃO DAR ERRO NO MARKDOWN
        html_card = f"""
<div style="background-color: #1E1E1E; padding: 20px; border-radius: 12px; border-left: 6px solid {cor_faixa}; box-shadow: 0 4px 10px rgba(0,0,0,0.4);">
<small style="color:#888; text-transform:uppercase; letter-spacing:1px;">Aluno Oficial</small>
<h3 style="margin:5px 0 0 0; color:white;">{user['nome_completo']}</h3>
<p style="margin:0 0 15px 0; color:#aaa; font-size:0.9em;">{user['email']}</p>
<div style="display:flex; gap:10px; align-items:center; margin-bottom:15px;">
<div style="background-color: {cor_faixa}; color: {cor_texto_tag}; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size:0.9em;">
{user['faixa']} {user['graus']}º
</div>
<div style="color:#ccc; font-size:0.9em;">
📍 {nome_filial}
</div>
</div>
<div style="background-color:#2b2b2b; padding:10px; border-radius:8px;">
<p style="margin:0; color:#888; font-size:0.8em;">TURMA ATUAL</p>
<p style="margin:2px 0 0 0; color:white; font-weight:500;">{nome_turma}</p>
<p style="margin:0; color:#aaa; font-size:0.8em;">{detalhes_turma}</p>
</div>
<p style="margin-top:15px; font-size:10px; color:#666; text-align:right;">Desde: {user['data_inicio']}</p>
</div>
"""
        st.markdown(html_card, unsafe_allow_html=True)

    with c_stats:
        total = db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s", (user['id'],), fetch=True)[0][0]
        presencas_marco = db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s AND data_aula >= %s", (user['id'], user['data_ultimo_grau'] or date.today()), fetch=True)[0][0]
        _, msg_meta, progresso, _ = utils.calcular_status_graduacao(user, presencas_marco)
        
        st.subheader("Minha Jornada 🥋")
        st.progress(progresso)
        st.caption(f"Status para próximo grau: {msg_meta}")
        
        k1, k2 = st.columns(2)
        k1.metric("Treinos (Total)", total)
        k2.metric("Treinos (Este Mês)", db.executar_query("SELECT COUNT(*) FROM checkins WHERE id_aluno=%s AND EXTRACT(MONTH FROM data_aula) = EXTRACT(MONTH FROM CURRENT_DATE)", (user['id'],), fetch=True)[0][0])

    # =======================================================
    # 4. HISTÓRICO RECENTE
    # =======================================================
    st.divider()
    with st.expander("📅 Ver Histórico de Presença"):
        hist = db.executar_query("SELECT data_aula, 'Presente' as status FROM checkins WHERE id_aluno=%s ORDER BY data_aula DESC LIMIT 10", (user['id'],), fetch=True)
        if hist: 
            df_hist = pd.DataFrame(hist, columns=['Data do Treino', 'Status'])
            df_hist['Data do Treino'] = pd.to_datetime(df_hist['Data do Treino']).dt.strftime('%d/%m/%Y')
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum treino registrado ainda.")