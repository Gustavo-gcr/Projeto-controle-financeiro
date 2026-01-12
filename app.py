import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import calendar
import time

# ==============================================================================
# 1. CONFIGURAÇÃO GERAL E ESTILO (CSS AVANÇADO)
# ==============================================================================
st.set_page_config(
    page_title="Gustavo Financial Intelligence | Pro",
    layout="wide",
    page_icon="🐺",
    initial_sidebar_state="expanded"
)

# Estilização CSS para modo Dark/Glassmorphism
st.markdown("""
    <style>
    /* Fundo Geral */
    .stApp {
        background-color: #0e1117;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }
    
    /* Cards de Métricas (Glassmorphism) */
    div[data-testid="metric-container"] {
        background: rgba(30, 35, 41, 0.7);
        border: 1px solid #30363d;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
        transition: transform 0.2s;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        border-color: #58a6ff;
    }
    
    /* Inputs Numéricos */
    .stNumberInput input {
        background-color: #0d1117 !important;
        color: #c9d1d9 !important;
        border: 1px solid #30363d;
        border-radius: 6px;
    }
    
    /* Botões */
    .stButton button {
        background-color: #238636;
        color: white;
        border: none;
        font-weight: bold;
        transition: 0.3s;
    }
    .stButton button:hover {
        background-color: #2ea043;
        box-shadow: 0 0 10px rgba(46, 160, 67, 0.5);
    }

    /* Títulos */
    h1, h2, h3 {
        color: #f0f6fc !important;
        font-family: 'Segoe UI', Helvetica, sans-serif;
        font-weight: 600;
    }
    
    /* Abas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #161b22;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #238636 !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. MOTOR DE DADOS E CONEXÃO (ROBUSTEZ MÁXIMA)
# ==============================================================================

MAPA_MESES = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}

class GerenciadorDados:
    """
    Classe responsável por toda a comunicação com o Firebase Firestore.
    Inclui tratamento de exceções e migração automática de esquema de dados.
    """
    def __init__(self):
        # Inicialização Singleton do Firebase
        if not firebase_admin._apps:
            try:
                # Tenta carregar dos segredos do Streamlit
                if "firebase" in st.secrets:
                    cred_dict = dict(st.secrets["firebase"])
                    cred = credentials.Certificate(cred_dict)
                    firebase_admin.initialize_app(cred)
                else:
                    st.error("❌ ERRO CRÍTICO: Segredos do Firebase não encontrados no `secrets.toml`.")
                    st.stop()
            except Exception as e:
                st.error(f"❌ Falha ao conectar ao banco de dados: {str(e)}")
                st.stop()
        
        self.db = firestore.client()

    def verificar_usuario(self, email):
        """Verifica se o usuário existe no banco de dados (case insensitive)."""
        if not email:
            return False
        try:
            email_formatado = email.strip().lower()
            doc = self.db.collection('usuarios').document(email_formatado).get()
            return doc.exists
        except Exception as e:
            st.error(f"Erro ao validar usuário: {e}")
            return False

    def carregar_configuracoes(self, email):
        """Carrega categorias do usuário ou cria padrão se não existir."""
        doc_ref = self.db.collection('usuarios').document(email)
        
        try:
            doc = doc_ref.get()
            
            # Estrutura padrão robusta
            config_padrao = {
                'receitas': ['Salário', 'Freelance', 'Dividendos', 'Bônus'],
                'despesas': ['Aluguel', 'Condomínio', 'Mercado', 'Lazer', 'Uber/Transporte', 'Saúde', 'Assinaturas', 'Educação'],
                'investimentos': ['CDB', 'Ações', 'FIIs', 'Cripto', 'Reserva de Emergência', 'Caixinha Nubank']
            }
            
            if not doc.exists:
                doc_ref.set(config_padrao)
                return config_padrao
            
            dados = doc.to_dict()
            
            # Migração de Schema: Garante que todas as chaves existam
            atualizou = False
            for chave, valor_padrao in config_padrao.items():
                if chave not in dados:
                    dados[chave] = valor_padrao
                    atualizou = True
            
            if atualizou:
                doc_ref.set(dados, merge=True)
                
            return dados
            
        except Exception as e:
            st.error(f"Erro ao carregar configurações: {e}")
            return {}

    def salvar_transacao(self, email, mes_ano, categoria, tipo, valor):
        """Salva ou atualiza uma transação no Firestore."""
        try:
            # Cria um ID único composto para evitar duplicatas erradas
            doc_id = f"{email}_{mes_ano}_{categoria.replace(' ', '_').lower()}"
            
            payload = {
                'email': email,
                'mes_ano': mes_ano,
                'categoria': categoria,
                'tipo': tipo,
                'valor': float(valor),
                'timestamp': firestore.SERVER_TIMESTAMP,
                'data_atualizacao': datetime.now().isoformat()
            }
            
            self.db.collection('lancamentos').document(doc_id).set(payload)
            return True
        except Exception as e:
            st.error(f"Erro ao salvar transação: {e}")
            return False

    def buscar_todos_dados(self, email):
        """Busca todo o histórico do usuário para processamento local (mais rápido)."""
        try:
            docs = self.db.collection('lancamentos').where('email', '==', email).stream()
            lista_dados = [d.to_dict() for d in docs]
            
            if not lista_dados:
                return pd.DataFrame(columns=['email', 'mes_ano', 'categoria', 'tipo', 'valor', 'timestamp'])
                
            df = pd.DataFrame(lista_dados)
            return df
        except Exception as e:
            st.error(f"Erro ao buscar dados: {e}")
            return pd.DataFrame()

    def gerenciar_categoria(self, email, tipo, categoria, acao='adicionar'):
        """Adiciona ou remove categorias do perfil do usuário."""
        mapa_campos = {'Receita': 'receitas', 'Despesa': 'despesas', 'Investimento': 'investimentos'}
        campo = mapa_campos.get(tipo)
        
        if not campo: return
        
        doc_ref = self.db.collection('usuarios').document(email)
        
        try:
            if acao == 'adicionar':
                doc_ref.update({campo: firestore.ArrayUnion([categoria])})
            elif acao == 'remover':
                doc_ref.update({campo: firestore.ArrayRemove([categoria])})
            return True
        except Exception as e:
            st.error(f"Erro ao atualizar categoria: {e}")
            return False

# Instancia o banco
db_manager = GerenciadorDados()

# ==============================================================================
# 3. INTERFACE DE AUTENTICAÇÃO
# ==============================================================================

def tela_login():
    """Renderiza a tela de login minimalista e centralizada."""
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    
    with c2:
        st.markdown(
            """
            <div style="text-align: center; padding: 20px; background-color: #161b22; border-radius: 10px; border: 1px solid #30363d;">
                <h1>🐺</h1>
                <h2>Gustavo Financial</h2>
                <p style='color: #8b949e;'>Acesso Restrito e Seguro</p>
            </div>
            """, 
            unsafe_allow_html=True
        )
        st.write("")
        
        with st.form("form_login"):
            email_input = st.text_input("Identificação (E-mail)", placeholder="seu@email.com").strip().lower()
            submit = st.form_submit_button("Acessar Sistema", use_container_width=True)
            
            if submit:
                if not email_input:
                    st.warning("⚠️ Por favor, digite seu e-mail.")
                else:
                    with st.spinner("Autenticando..."):
                        if db_manager.verificar_usuario(email_input):
                            st.session_state['usuario_logado'] = email_input
                            st.success("✅ Acesso Autorizado!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("⛔ Acesso Negado. Usuário não encontrado na base segura.")

# ==============================================================================
# 4. APLICAÇÃO PRINCIPAL (CORE)
# ==============================================================================

def app_principal():
    usuario = st.session_state['usuario_logado']
    
    # --- BARRA LATERAL (SIDEBAR) ---
    with st.sidebar:
        st.title(f"Olá, Gustavo")
        st.caption(f"ID: {usuario}")
        
        if st.button("🔒 Sair do Sistema", use_container_width=True):
            st.session_state['usuario_logado'] = None
            st.rerun()
            
        st.markdown("---")
        
        # Seletores de Data
        st.subheader("📅 Período de Análise")
        ano_atual = datetime.now().year
        ano_sel = st.selectbox("Ano de Referência", [ano_atual-1, ano_atual, ano_atual+1], index=1)
        
        mes_atual_index = datetime.now().month - 1
        mes_nome_sel = st.selectbox("Mês de Referência", list(MAPA_MESES.values()), index=mes_atual_index)
        
        # Lógica para chave de data (YYYY-MM)
        mes_num = [k for k, v in MAPA_MESES.items() if v == mes_nome_sel][0]
        chave_mes = f"{ano_sel}-{mes_num:02d}"
        
        st.info(f"Visualizando dados de: **{mes_nome_sel}/{ano_sel}**")
        
        st.markdown("---")
        
        # Configurações Rápidas de Meta
        st.subheader("🎯 Metas")
        meta_poupanca = st.slider("Meta de Aporte (%)", min_value=0, max_value=100, value=30, step=5)
        
        st.markdown("---")
        menu_nav = st.radio(
            "Navegação Principal", 
            ["📝 Lançamentos", "📊 Dashboard Pro", "📈 Visão Anual", "⚙️ Sistema"]
        )

    # --- CARREGAMENTO DE DADOS ---
    df_completo = db_manager.buscar_todos_dados(usuario)
    config_usuario = db_manager.carregar_configuracoes(usuario)
    
    # Filtragens
    df_mes_atual = pd.DataFrame()
    df_ano_atual = pd.DataFrame()
    
    if not df_completo.empty:
        df_mes_atual = df_completo[df_completo['mes_ano'] == chave_mes].copy()
        df_ano_atual = df_completo[df_completo['mes_ano'].str.startswith(str(ano_sel))].copy()
    
    # Mapeamento de valores para preencher inputs
    mapa_valores = {}
    if not df_mes_atual.empty:
        for index, row in df_mes_atual.iterrows():
            mapa_valores[row['categoria']] = row['valor']

    # ==========================================================================
    # ABA 1: LANÇAMENTOS (LÓGICA CORRIGIDA E SEGURA)
    # ==========================================================================
    if menu_nav == "📝 Lançamentos":
        st.title(f"Gestão de Caixa: {mes_nome_sel} de {ano_sel}")
        st.markdown("Insira os valores acumulados do mês. O sistema salva automaticamente ao alterar o valor.")
        
        tab1, tab2, tab3 = st.tabs(["🟢 Entradas (Receitas)", "🔵 Aportes (Investimentos)", "🔴 Saídas (Despesas)"])
        
        # --- TAB RECEITAS ---
        with tab1:
            st.subheader("Fontes de Renda")
            col_r1, col_r2 = st.columns([2, 1])
            total_receitas = 0.0
            
            with col_r1:
                with st.container(border=True):
                    cols = st.columns(2)
                    idx = 0
                    lista_investimentos = config_usuario.get('investimentos', [])
                    
                    for categoria in config_usuario.get('receitas', []):
                        # --- TRAVA DE SEGURANÇA SOLICITADA ---
                        # Se a categoria estiver na lista de investimentos, pula silenciosamente
                        if categoria in lista_investimentos:
                            continue
                        # -------------------------------------
                        
                        col_atual = cols[idx % 2]
                        val_inicial = float(mapa_valores.get(categoria, 0.0))
                        
                        novo_valor = col_atual.number_input(
                            f"💰 {categoria}", 
                            value=val_inicial, 
                            step=100.0, 
                            min_value=0.0,
                            key=f"in_{chave_mes}_{categoria}"
                        )
                        
                        if novo_valor != val_inicial:
                            db_manager.salvar_transacao(usuario, chave_mes, categoria, 'Receita', novo_valor)
                            
                        total_receitas += novo_valor
                        idx += 1
            
            with col_r2:
                st.metric(label="TOTAL RECEITAS", value=f"R$ {total_receitas:,.2f}")
                st.info("💡 Dica: Rendimentos de investimentos devem ser lançados aqui apenas se forem sacados para uso.")

        # --- TAB INVESTIMENTOS ---
        with tab2:
            st.subheader("Construção de Patrimônio")
            col_i1, col_i2 = st.columns([2, 1])
            total_investido = 0.0
            
            with col_i1:
                with st.container(border=True):
                    cols = st.columns(2)
                    idx = 0
                    for categoria in config_usuario.get('investimentos', []):
                        col_atual = cols[idx % 2]
                        val_inicial = float(mapa_valores.get(categoria, 0.0))
                        
                        novo_valor = col_atual.number_input(
                            f"📈 {categoria}", 
                            value=val_inicial, 
                            step=100.0, 
                            min_value=0.0,
                            key=f"inv_{chave_mes}_{categoria}"
                        )
                        
                        if novo_valor != val_inicial:
                            db_manager.salvar_transacao(usuario, chave_mes, categoria, 'Investimento', novo_valor)
                            
                        total_investido += novo_valor
                        idx += 1
            
            with col_i2:
                st.metric(label="TOTAL APORTADO", value=f"R$ {total_investido:,.2f}")
                perc = (total_investido / total_receitas * 100) if total_receitas > 0 else 0
                st.progress(min(perc/100, 1.0))
                st.caption(f"Você investiu {perc:.1f}% da sua renda este mês.")

        # --- TAB DESPESAS ---
        with tab3:
            st.subheader("Controle de Gastos")
            col_d1, col_d2 = st.columns([3, 1])
            total_despesas = 0.0
            
            with col_d1:
                with st.container(border=True):
                    cols = st.columns(3) # 3 colunas para despesas pois são muitas
                    idx = 0
                    for categoria in config_usuario.get('despesas', []):
                        col_atual = cols[idx % 3]
                        val_inicial = float(mapa_valores.get(categoria, 0.0))
                        
                        novo_valor = col_atual.number_input(
                            f"💸 {categoria}", 
                            value=val_inicial, 
                            step=50.0, 
                            min_value=0.0,
                            key=f"out_{chave_mes}_{categoria}"
                        )
                        
                        if novo_valor != val_inicial:
                            db_manager.salvar_transacao(usuario, chave_mes, categoria, 'Despesa', novo_valor)
                            
                        total_despesas += novo_valor
                        idx += 1
            
            with col_d2:
                st.metric(label="TOTAL GASTOS", value=f"R$ {total_despesas:,.2f}")
                if total_receitas > 0:
                    perc_gastos = (total_despesas / total_receitas * 100)
                    st.write(f"Commitment: **{perc_gastos:.1f}%** da renda.")

    # ==========================================================================
    # ABA 2: DASHBOARD PRO (MAIS DE 7 GRÁFICOS)
    # ==========================================================================
    elif menu_nav == "📊 Dashboard Pro":
        st.title(f"Intelligence Dashboard: {mes_nome_sel}")
        
        if df_mes_atual.empty:
            st.warning("⚠️ Sem dados suficientes neste mês. Vá em 'Lançamentos' e preencha as informações.")
        else:
            # Cálculos Base
            rec = df_mes_atual[df_mes_atual['tipo']=='Receita']['valor'].sum()
            desp = df_mes_atual[df_mes_atual['tipo']=='Despesa']['valor'].sum()
            inv = df_mes_atual[df_mes_atual['tipo']=='Investimento']['valor'].sum()
            saldo = rec - desp - inv
            taxa_poupanca_real = (inv / rec * 100) if rec > 0 else 0

            # --- LINHA 1: KPIS (GLASS CARDS) ---
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Receita Líquida", f"R$ {rec:,.2f}", help="Total ganho no mês")
            k2.metric("Despesas Totais", f"R$ {desp:,.2f}", delta=f"{(desp/rec*100 if rec else 0):.1f}%", delta_color="inverse", help="Total gasto")
            k3.metric("Investimentos", f"R$ {inv:,.2f}", delta=f"{taxa_poupanca_real:.1f}%", help="Total guardado")
            k4.metric("Caixa Livre", f"R$ {saldo:,.2f}", delta_color="off" if saldo >= 0 else "inverse", help="Sobra final")
            
            st.markdown("---")

            # --- LINHA 2: FLUXO E META (GRÁFICOS 1 e 2) ---
            g1, g2 = st.columns([2, 1])
            
            with g1:
                st.subheader("1. Fluxo de Caixa (Waterfall)")
                # Prepara dados waterfall
                cats = df_mes_atual[df_mes_atual['tipo'].isin(['Despesa', 'Investimento'])]['categoria'].tolist()
                vals = [-x for x in df_mes_atual[df_mes_atual['tipo'].isin(['Despesa', 'Investimento'])]['valor'].tolist()]
                
                fig_water = go.Figure(go.Waterfall(
                    orientation = "v",
                    measure = ["relative"] * (len(vals) + 1) + ["total"],
                    x = ["Entrada"] + cats + ["Saldo Final"],
                    y = [rec] + vals + [saldo],
                    connector = {"line": {"color": "rgba(255,255,255,0.5)"}},
                    decreasing = {"marker": {"color": "#ef553b"}},
                    increasing = {"marker": {"color": "#238636"}},
                    totals = {"marker": {"color": "#1f6feb"}}
                ))
                fig_water.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=400)
                st.plotly_chart(fig_water, use_container_width=True)
            
            with g2:
                st.subheader("2. Meta de Aporte")
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = taxa_poupanca_real,
                    title = {'text': f"Meta: {meta_poupanca}%"},
                    gauge = {
                        'axis': {'range': [0, 60]},
                        'bar': {'color': "#238636"},
                        'steps': [
                            {'range': [0, meta_poupanca*0.5], 'color': "#8c1b1b"},
                            {'range': [meta_poupanca*0.5, meta_poupanca], 'color': "#d4a72c"}
                        ],
                        'threshold': {
                            'line': {'color': "white", 'width': 4},
                            'thickness': 0.75,
                            'value': meta_poupanca
                        }
                    }
                ))
                fig_gauge.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', height=400)
                st.plotly_chart(fig_gauge, use_container_width=True)

            # --- LINHA 3: DETALHAMENTO HIERÁRQUICO (GRÁFICOS 3 e 4) ---
            g3, g4 = st.columns(2)
            
            with g3:
                st.subheader("3. Raio-X de Saídas (Sunburst)")
                df_saidas = df_mes_atual[df_mes_atual['tipo'].isin(['Despesa', 'Investimento'])]
                if not df_saidas.empty:
                    fig_sun = px.sunburst(
                        df_saidas, 
                        path=['tipo', 'categoria'], 
                        values='valor', 
                        color='tipo',
                        color_discrete_map={'Despesa': '#ef553b', 'Investimento': '#238636'}
                    )
                    fig_sun.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_sun, use_container_width=True)
            
            with g4:
                st.subheader("4. Mapa de Volume (Treemap)")
                if not df_saidas.empty:
                    fig_tree = px.treemap(
                        df_saidas,
                        path=['tipo', 'categoria'],
                        values='valor',
                        color='valor',
                        color_continuous_scale='Blackbody'
                    )
                    fig_tree.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_tree, use_container_width=True)

            # --- LINHA 4: ESTATÍSTICA E OUTLIERS (GRÁFICOS 5 e 6) ---
            g5, g6 = st.columns(2)
            
            with g5:
                st.subheader("5. Distribuição de Valores (Boxplot)")
                # Analisa a variabilidade dos gastos
                df_desp = df_mes_atual[df_mes_atual['tipo']=='Despesa']
                if not df_desp.empty:
                    fig_box = px.box(df_desp, x='tipo', y='valor', points="all", color_discrete_sequence=['#ef553b'])
                    fig_box.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', title="Dispersão das Despesas")
                    st.plotly_chart(fig_box, use_container_width=True)
            
            with g6:
                st.subheader("6. Análise de Impacto (Scatter)")
                # Gráfico de bolhas
                fig_scat = px.scatter(
                    df_mes_atual, 
                    x='categoria', 
                    y='valor', 
                    color='tipo', 
                    size='valor', 
                    size_max=50,
                    color_discrete_map={'Receita': '#1f6feb', 'Despesa': '#ef553b', 'Investimento': '#238636'}
                )
                fig_scat.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_scat, use_container_width=True)

            # --- LINHA 5: RANKING E COMPOSIÇÃO (GRÁFICOS 7, 8 e 9) ---
            g7, g8 = st.columns([2, 1])
            
            with g7:
                st.subheader("7. Top Maiores Gastos (Ranking)")
                df_rank = df_mes_atual[df_mes_atual['tipo']=='Despesa'].nlargest(7, 'valor').sort_values('valor', ascending=True)
                if not df_rank.empty:
                    fig_barh = px.bar(
                        df_rank, 
                        x='valor', 
                        y='categoria', 
                        orientation='h', 
                        text_auto='.2s', 
                        color='valor', 
                        color_continuous_scale='Reds'
                    )
                    fig_barh.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
                    st.plotly_chart(fig_barh, use_container_width=True)
            
            with g8:
                st.subheader("8. Composição Geral")
                resumo_tipo = df_mes_atual.groupby('tipo')['valor'].sum().reset_index()
                fig_donut = px.pie(
                    resumo_tipo, 
                    values='valor', 
                    names='tipo', 
                    hole=0.6,
                    color='tipo',
                    color_discrete_map={'Receita': '#1f6feb', 'Despesa': '#ef553b', 'Investimento': '#238636'}
                )
                fig_donut.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
                st.plotly_chart(fig_donut, use_container_width=True)

            # --- GRÁFICO 9 (NOVO): EVOLUÇÃO TEMPORAL ---
            # Como salvamos a data de atualização, podemos simular uma "linha do tempo" se houver dados
            st.subheader("9. Evolução dos Lançamentos")
            fig_bar_v = px.bar(
                df_mes_atual, 
                x='categoria', 
                y='valor', 
                color='tipo', 
                barmode='group',
                color_discrete_map={'Receita': '#1f6feb', 'Despesa': '#ef553b', 'Investimento': '#238636'}
            )
            fig_bar_v.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', height=300)
            st.plotly_chart(fig_bar_v, use_container_width=True)

    # ==========================================================================
    # ABA 3: VISÃO ANUAL (MACRO)
    # ==========================================================================
    elif menu_nav == "📈 Visão Anual":
        st.title(f"Panorama Estratégico: {ano_sel}")
        
        if df_ano_atual.empty:
            st.info(f"Sem dados suficientes para o ano de {ano_sel}. Comece lançando dados mensais.")
        else:
            # Pivotamento de dados para visão anual
            pivot_anual = df_ano_atual.pivot_table(index='mes_ano', columns='tipo', values='valor', aggfunc='sum', fill_value=0)
            
            # Garante colunas mesmo que zeradas
            for c in ['Receita', 'Despesa', 'Investimento']:
                if c not in pivot_anual: pivot_anual[c] = 0.0
            
            pivot_anual['Saldo'] = pivot_anual['Receita'] - pivot_anual['Despesa'] - pivot_anual['Investimento']
            pivot_anual['Patrimonio_Acumulado'] = pivot_anual['Investimento'].cumsum()

            # Métricas Anuais
            tot_rec_ano = pivot_anual['Receita'].sum()
            tot_inv_ano = pivot_anual['Investimento'].sum()
            st.markdown(f"### Você movimentou **R$ {tot_rec_ano:,.2f}** em {ano_sel}")
            
            a1, a2 = st.columns(2)
            
            with a1:
                st.subheader("Curva de Patrimônio (Acumulado)")
                fig_pat = px.area(pivot_anual, x=pivot_anual.index, y='Patrimonio_Acumulado', markers=True)
                fig_pat.update_traces(line_color='#00cc96')
                fig_pat.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_pat, use_container_width=True)
            
            with a2:
                st.subheader("Comparativo Mensal")
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Bar(x=pivot_anual.index, y=pivot_anual['Receita'], name='Entrada', marker_color='#1f6feb'))
                fig_comp.add_trace(go.Bar(x=pivot_anual.index, y=pivot_anual['Despesa'], name='Saída', marker_color='#ef553b'))
                fig_comp.add_trace(go.Bar(x=pivot_anual.index, y=pivot_anual['Investimento'], name='Aporte', marker_color='#238636'))
                fig_comp.update_layout(barmode='group', template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_comp, use_container_width=True)
            
            # Heatmap de Gastos
            st.subheader("Mapa de Calor de Despesas (Sazonalidade)")
            df_desp_ano = df_ano_atual[df_ano_atual['tipo']=='Despesa']
            if not df_desp_ano.empty:
                heat_data = df_desp_ano.pivot_table(index='categoria', columns='mes_ano', values='valor', aggfunc='sum', fill_value=0)
                fig_heat = px.imshow(heat_data, color_continuous_scale='Magma', text_auto=True, aspect="auto")
                fig_heat.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', height=600)
                st.plotly_chart(fig_heat, use_container_width=True)

    # ==========================================================================
    # ABA 4: CONFIGURAÇÕES DO SISTEMA
    # ==========================================================================
    elif menu_nav == "⚙️ Sistema":
        st.header("Configurações Globais")
        st.markdown("Gerencie as categorias disponíveis para seus lançamentos.")
        
        c_add, c_del = st.columns(2)
        
        # --- ADICIONAR ---
        with c_add:
            with st.container(border=True):
                st.subheader("➕ Adicionar Categoria")
                tipo_add = st.selectbox("Tipo da Nova Categoria", ["Receita", "Despesa", "Investimento"])
                nome_add = st.text_input("Nome da Categoria").strip()
                
                if st.button("Confirmar Inclusão"):
                    if nome_add:
                        if db_manager.gerenciar_categoria(usuario, tipo_add, nome_add, 'adicionar'):
                            st.success(f"Categoria '{nome_add}' adicionada com sucesso!")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.warning("Digite um nome válido.")

        # --- REMOVER (NOVO RECURSO) ---
        with c_del:
            with st.container(border=True):
                st.subheader("🗑️ Remover Categoria")
                tipo_del = st.selectbox("Tipo para Remover", ["Receita", "Despesa", "Investimento"], key="del_sel")
                
                # Lista atual baseada no tipo selecionado
                chave_map = {'Receita': 'receitas', 'Despesa': 'despesas', 'Investimento': 'investimentos'}
                lista_atual = config_usuario.get(chave_map[tipo_del], [])
                
                cat_del = st.selectbox("Selecione para excluir", lista_atual)
                
                if st.button("Confirmar Exclusão", type="primary"):
                    if cat_del:
                        if db_manager.gerenciar_categoria(usuario, tipo_del, cat_del, 'remover'):
                            st.success(f"Categoria '{cat_del}' removida!")
                            time.sleep(1)
                            st.rerun()

# ==============================================================================
# 5. INICIALIZAÇÃO E CONTROLE DE SESSÃO
# ==============================================================================
if 'usuario_logado' not in st.session_state:
    st.session_state['usuario_logado'] = None

if st.session_state['usuario_logado']:
    app_principal()
else:
    tela_login()