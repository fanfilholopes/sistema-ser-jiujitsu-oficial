import streamlit as st
import database as db
import utils
import pandas as pd
from datetime import date
# Importação explícita do novo motor para garantir acesso às funções
from core.motores_graduacao import calcular_status_graduacao
import time
import os

def painel_professor():
    user = st.session_state.usuario
    id_filial_origem = user['id_filial']
    id_prof = user['id']
    perfil = user.get('perfil', 'professor')

    # =======================================================
    # --- SIDEBAR PADRONIZADA ---
    # =======================================================
    
    # 1. FOTO DO USUÁRIO LOGADO
    foto_url = user.get('foto_perfil')
    
    col_foto, col_vazia = st.sidebar.columns([1, 0.2])
    with col_foto:
        if foto_url and os.path.exists(foto_url):
            try: 
                st.image(foto_url, width=120)
            except: 
                st.markdown("## 👤")
        else:
            st.markdown("## 👤") # Fallback se não tiver foto

    st.sidebar.markdown(f"### {user['nome_completo']}")
    cargo_texto = utils.CARGOS.get(perfil, perfil).upper()
    st.sidebar.caption(f"🛡️ {cargo_texto}")
    
    # 2. BOTÃO DE "MEU PERFIL" (UPLOAD DE FOTO)
    with st.sidebar.popover("⚙️ Meu Perfil", use_container_width=True):
        st.markdown("#### Atualizar Foto")
        nova_foto = st.file_uploader("Escolha uma imagem", type=["jpg", "jpeg", "png"])
        
        if nova_foto is not None:
            if st.button("💾 Salvar Foto", use_container_width=True):
                pasta_fotos = "fotos_perfil"
                os.makedirs(pasta_fotos, exist_ok=True)
                
                caminho_foto = os.path.join(pasta_fotos, f"user_{user['id']}_{nova_foto.name}")
                with open(caminho_foto, "wb") as f:
                    f.write(nova_foto.getbuffer())
                
                db.executar_query("UPDATE usuarios SET foto_perfil=%s WHERE id=%s", (caminho_foto, user['id']))
                st.session_state.usuario['foto_perfil'] = caminho_foto
                
                st.success("Foto atualizada! Oss!")
                time.sleep(1)
                st.rerun()

    st.sidebar.markdown("---")
    
    if st.sidebar.button("Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

    # 3. LOGO DO SISTEMA NO RODAPÉ
    st.sidebar.markdown("<br><br><br><br>", unsafe_allow_html=True)
    try:
        st.sidebar.image("logoser.jpg", use_container_width=True)
    except:
        pass

    # =======================================================
    # --- ABA ÚNICA: GESTÃO DE TATAME ---
    # =======================================================
    st.title("🛡️ Gestão de Tatame")
    
    # 1. VALIDAÇÃO DE CHECK-INS (O ACEITE)
    st.subheader("🔔 Check-ins Pendentes de Aceite")
    
    sql_pendencias = """
        SELECT c.id, u.nome_completo, t.nome as turma, t.horario, f.nome as nome_filial
        FROM checkins c
        JOIN usuarios u ON c.id_aluno = u.id
        JOIN turmas t ON c.id_turma = t.id
        JOIN filiais f ON c.id_filial = f.id
        WHERE c.data_aula = CURRENT_DATE 
        AND c.validado = FALSE
        AND (t.id_professor = %s OR c.id_filial = %s)
        ORDER BY t.horario
    """
    pendencias = db.executar_query(sql_pendencias, (id_prof, id_filial_origem), fetch=True)

    if pendencias:
        st.info(f"Você tem {len(pendencias)} alunos aguardando liberação para o treino.")
        
        for p in pendencias:
            with st.container(border=True):
                c_info, c_btn = st.columns([3, 1.2])
                c_info.markdown(f"**{p['nome_completo']}**")
                txt_local = f" | 🏢 {p['nome_filial']}" if p['nome_filial'] else ""
                c_info.caption(f"Turma: {p['turma']} às {p['horario']}{txt_local}")
                
                col_ok, col_no = c_btn.columns(2)
                if col_ok.button("✅", key=f"ok_{p['id']}", help="Aceitar Presença", use_container_width=True):
                    db.executar_query("UPDATE checkins SET validado=TRUE WHERE id=%s", (p['id'],))
                    st.toast(f"{p['nome_completo']} confirmado!"); time.sleep(0.5); st.rerun()
                
                if col_no.button("❌", key=f"no_{p['id']}", help="Recusar", use_container_width=True):
                    db.executar_query("DELETE FROM checkins WHERE id=%s", (p['id'],))
                    st.toast("Check-in recusado."); time.sleep(0.5); st.rerun()
    else:
        st.success("Tudo limpo! Nenhum check-in pendente agora.")

    st.divider()

    # 2. LISTA DE PRESENÇA JÁ VALIDADA
    st.subheader("✅ Confirmados no Tatame Hoje")
    
    sql_confirmados = """
        SELECT u.nome_completo, t.nome as turma, u.faixa, f.nome as nome_filial
        FROM checkins c
        JOIN usuarios u ON c.id_aluno = u.id
        JOIN turmas t ON c.id_turma = t.id
        JOIN filiais f ON c.id_filial = f.id
        WHERE c.data_aula = CURRENT_DATE 
        AND c.validado = TRUE
        AND (t.id_professor = %s OR c.id_filial = %s)
        ORDER BY t.horario DESC
    """
    confirmados = db.executar_query(sql_confirmados, (id_prof, id_filial_origem), fetch=True)
    
    if confirmados:
        for c in confirmados:
            st.markdown(f"- **{c['nome_completo']}** ({c['faixa']}) <span style='color:grey'>| {c['turma']} ({c['nome_filial']})</span>", unsafe_allow_html=True)
    else:
        st.caption("Nenhum aluno confirmado ainda.")

    st.divider()

    # =======================================================
    # --- 3. GESTÃO DE GRADUAÇÕES (OTIMIZADO) ---
    # =======================================================
    st.subheader("🎓 Monitoramento de Graduações")
    
    # Buscamos todos os alunos vinculados à filial do professor
    sql_meus_alunos = """
        SELECT id, nome_completo, faixa, graus, data_nascimento, data_ultimo_grau, data_inicio
        FROM usuarios 
        WHERE perfil = 'aluno' 
        AND id_filial = %s
        ORDER BY nome_completo
    """
    meus_alunos = db.executar_query(sql_meus_alunos, (id_filial_origem,), fetch=True)

    if meus_alunos:
        # --- OTIMIZAÇÃO: BUSCA DE PRESENÇAS EM LOTE ---
        # Buscamos a contagem de presenças de TODOS os alunos de uma vez
        sql_lote_presencas = """
            SELECT id_aluno, COUNT(*) as total 
            FROM checkins 
            WHERE id_filial = %s AND validado = TRUE 
            GROUP BY id_aluno
        """
        res_lote = db.executar_query(sql_lote_presencas, (id_filial_origem,), fetch=True)
        # Criamos um mapa {id_aluno: total_presencas} para consulta rápida em memória
        mapa_presencas = {r['id_aluno']: r['total'] for r in res_lote} if res_lote else {}

        st.caption("Acompanhe o progresso técnico e assiduidade dos seus alunos.")
        
        for aluno in meus_alunos:
            total_presencas = mapa_presencas.get(aluno['id'], 0)
            data_ref = aluno.get('data_ultimo_grau') or aluno.get('data_inicio') or date(2020, 1, 1)
            
            # CONSULTA AO MOTOR DE GRADUAÇÃO (O novo motor retorna 3 valores)
            apto, msg, is_faixa = calcular_status_graduacao(aluno, total_presencas)
            
            # Formatação visual de acordo com o status
            cor_status = "green" if apto else "orange"
            icone = "🔥" if (apto and is_faixa) else ("🎓" if apto else "⏳")
            
            # Interface Visual por Aluno (Expander)
            with st.expander(f"👤 {aluno['nome_completo']} | {aluno['faixa']} ({aluno['graus']}º Grau)"):
                c1, c2 = st.columns([3, 1.2])
                
                with c1:
                    st.markdown(f"**Status:** :{cor_status}[{icone} {msg}]")
                    st.caption(f"🥋 {total_presencas} aulas computadas desde {data_ref.strftime('%d/%m/%Y')}")

                with c2:
                    # Botão só aparece se o aluno estiver 100% apto
                    if apto:
                        if is_faixa:
                            if st.button("Indicar Faixa", key=f"btn_faixa_{aluno['id']}", use_container_width=True, type="primary"):
                                sql_sol = """
                                    INSERT INTO solicitacoes_graduacao (id_aluno, id_filial, faixa_atual, status) 
                                    VALUES (%s, %s, %s, 'Pendente')
                                """
                                db.executar_query(sql_sol, (aluno['id'], id_filial_origem, aluno['faixa']))
                                st.success("Solicitação enviada!")
                                time.sleep(1)
                                st.rerun()
                        else:
                            if st.button("Conceder Grau", key=f"btn_grau_{aluno['id']}", use_container_width=True, type="primary"):
                                sucesso = db.registrar_grau_direto(aluno['id'], id_prof)
                                if sucesso:
                                    st.balloons()
                                    st.success("Grau registrado!")
                                    time.sleep(1)
                                    st.rerun()
                    # Quando NÃO estiver apto, nenhum botão inútil será renderizado. A interface fica limpa.
    else:
        st.info("Nenhum aluno encontrado para monitoramento nesta filial.")

# Execução do painel
if __name__ == "__main__":
    painel_professor()