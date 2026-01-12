import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import calendar

# ==============================================================================
# 1. CONFIGURAÇÃO VISUAL (CSS PROFISSIONAL & DARK MODE)
# ==============================================================================
st.set_page_config(
    page_title="Gustavo Financial Intelligence",
    layout="wide",
    page_icon="🐺",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    /* Fundo Geral */
    .stApp { background-color: #0b0e11; }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #15191e;
        border-right: 1px solid #2d333b;
    }
    
    /* Métricas (Cards) */
    div[data-testid="metric-container"] {
        background-color: #1e2329;
        border: 1px solid #2d333b;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    /* Inputs */
    .stNumberInput input { background-color: #0d1117 !important; color: white !important; border-radius: 4px; }
    
    /* Títulos */
    h1, h2, h3 { color: #e6edf3 !important; font-family: 'Segoe UI', sans-serif; font-weight: 600; }
    
    /* Gráficos */
    .js-plotly-plot .plotly .modebar { display: none !important; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. MOTOR DE DADOS (LÓGICA CORRIGIDA)
# ==============================================================================

MAPA_MESES = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}

class BancoDeDados:
    def __init__(self):
        if not firebase_admin._apps:
            try:
                cred_dict = dict(st.secrets["firebase"])
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
            except Exception as e:
                st.error(f"Erro de Conexão: {e}")
                st.stop()
        self.db = firestore.client()

    def verificar_usuario(self, email):
        if not email: return False
        try:
            return self.db.collection('usuarios').document(email.strip().lower()).get().exists
        except: return False

    def pegar_config(self, email):
        doc_ref = self.db.collection('usuarios').document(email)
        doc = doc_ref.get()
        
        # CATEGORIAS PADRÃO (SEPARADAS CORRETAMENTE)
        padrao = {
            'receitas': ['Salário', 'Freelance', 'Dividendos'],
            'despesas': ['Aluguel', 'Mercado', 'Lazer', 'Cartão de Crédito', 'Uber/Transporte', 'Assinaturas'],
            'investimentos': ['CDB', 'Ações', 'FIIs', 'Caixinha Nubank', 'Reserva de Emergência']
        }
        
        if not doc.exists:
            doc_ref.set(padrao)
            return padrao
        
        dados = doc.to_dict()
        # Migração automática se faltar alguma chave
        mudou = False
        for k in padrao.keys():
            if k not in dados:
                dados[k] = padrao[k]
                mudou = True
        if mudou:
            doc_ref.set(dados, merge=True)
            
        return dados

    def salvar_transacao(self, email, mes_ano, categoria, tipo, valor):
        doc_id = f"{email}_{mes_ano}_{categoria.replace(' ', '_').lower()}"
        payload = {
            'email': email, 'mes_ano': mes_ano, 'categoria': categoria,
            'tipo': tipo, 'valor': float(valor), 'timestamp': firestore.SERVER_TIMESTAMP
        }
        self.db.collection('lancamentos').document(doc_id).set(payload)

    def buscar_tudo(self, email):
        """Busca tudo de uma vez para filtrar no Python e evitar erros de índice do Firebase"""
        docs = self.db.collection('lancamentos').where('email', '==', email).stream()
        lista = [d.to_dict() for d in docs]
        return pd.DataFrame(lista)

    def add_categoria(self, email, tipo, nova_cat):
        mapa = {'Receita': 'receitas', 'Despesa': 'despesas', 'Investimento': 'investimentos'}
        self.db.collection('usuarios').document(email).update({mapa[tipo]: firestore.ArrayUnion([nova_cat])})

db = BancoDeDados()

# ==============================================================================
# 3. INTERFACE (FRONTEND)
# ==============================================================================

def login_screen():
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<br><br><h1 style='text-align: center;'>🔐 Acesso Gustavo</h1>", unsafe_allow_html=True)
        with st.form("login"):
            email = st.text_input("E-mail").strip().lower()
            if st.form_submit_button("Entrar", use_container_width=True):
                if db.verificar_usuario(email):
                    st.session_state['user'] = email
                    st.rerun()
                else:
                    st.error("Acesso não autorizado.")

def main_app():
    user = st.session_state['user']
    
    # --- SIDEBAR (FIXA E LIMPA) ---
    with st.sidebar:
        # NOME FIXO COMO PEDIDO
        st.title("👤 Gustavo")
        if st.button("Sair", use_container_width=True):
            st.session_state['user'] = None
            st.rerun()
            
        st.divider()
        
        # DATA
        st.caption("CONFIGURAÇÃO DE DATA")
        ano_atual = datetime.now().year
        sel_ano = st.selectbox("Ano", [ano_atual-1, ano_atual, ano_atual+1], index=1)
        
        mes_atual_idx = datetime.now().month - 1
        sel_mes_nome = st.selectbox("Mês", list(MAPA_MESES.values()), index=mes_atual_idx)
        
        # Lógica YYYY-MM
        mes_num = [k for k, v in MAPA_MESES.items() if v == sel_mes_nome][0]
        mes_chave = f"{sel_ano}-{mes_num:02d}"
        
        st.success(f"🗓️ {sel_mes_nome}/{sel_ano}")
        
        st.divider()
        menu = st.radio("NAVEGAÇÃO", ["📝 Lançamentos", "📊 Dashboard Mensal", "📈 Visão Anual", "⚙️ Configurações"])

    # --- CARREGAMENTO DE DADOS (GLOBAL) ---
    df_full = db.buscar_tudo(user)
    config = db.pegar_config(user)
    
    # Filtra Mês Atual
    if not df_full.empty:
        df_mes = df_full[df_full['mes_ano'] == mes_chave]
        # Filtra Ano Atual
        df_ano = df_full[df_full['mes_ano'].str.startswith(str(sel_ano))]
    else:
        df_mes = pd.DataFrame()
        df_ano = pd.DataFrame()
        
    val_map = {row['categoria']: row['valor'] for _, row in df_mes.iterrows()} if not df_mes.empty else {}

    # ==========================================================================
    # ABA 1: LANÇAMENTOS (Separado Corretamente)
    # ==========================================================================
    if menu == "📝 Lançamentos":
        st.header(f"Gestão de Caixa: {sel_mes_nome}")
        
        c1, c2, c3 = st.columns(3)
        
        # 1. RECEITAS
        with c1:
            st.subheader("🟢 Entradas")
            st.caption("Dinheiro que entrou na conta")
            with st.container(border=True):
                tot_rec = 0.0
                for cat in config.get('receitas', []):
                    # Removemos 'Investimentos' daqui se por acaso estivesse no config antigo
                    if cat in config.get('investimentos', []): continue 
                    
                    key = f"in_{mes_chave}_{cat}"
                    val = st.number_input(cat, value=float(val_map.get(cat, 0.0)), step=100.0, key=key)
                    if val != val_map.get(cat, 0.0): db.salvar_transacao(user, mes_chave, cat, 'Receita', val)
                    tot_rec += val
                st.metric("Total Entradas", f"R$ {tot_rec:,.2f}")

        # 2. INVESTIMENTOS (Separado!)
        with c2:
            st.subheader("🔵 Aportes/Investimentos")
            st.caption("Dinheiro guardado para o futuro")
            with st.container(border=True):
                tot_inv = 0.0
                for cat in config.get('investimentos', []):
                    key = f"inv_{mes_chave}_{cat}"
                    val = st.number_input(cat, value=float(val_map.get(cat, 0.0)), step=100.0, key=key)
                    if val != val_map.get(cat, 0.0): db.salvar_transacao(user, mes_chave, cat, 'Investimento', val)
                    tot_inv += val
                st.metric("Total Aportado", f"R$ {tot_inv:,.2f}")

        # 3. DESPESAS
        with c3:
            st.subheader("🔴 Despesas")
            st.caption("Dinheiro gasto/perdido")
            with st.container(border=True):
                tot_desp = 0.0
                for cat in config.get('despesas', []):
                    key = f"out_{mes_chave}_{cat}"
                    val = st.number_input(cat, value=float(val_map.get(cat, 0.0)), step=50.0, key=key)
                    if val != val_map.get(cat, 0.0): db.salvar_transacao(user, mes_chave, cat, 'Despesa', val)
                    tot_desp += val
                st.metric("Total Gastos", f"R$ {tot_desp:,.2f}")

    # ==========================================================================
    # ABA 2: DASHBOARD MENSAL (GRÁFICOS 1, 2, 3, 4)
    # ==========================================================================
    elif menu == "📊 Dashboard Mensal":
        st.title(f"Análise Tática: {sel_mes_nome}")
        
        if df_mes.empty:
            st.warning("Preencha os lançamentos para ver os gráficos.")
        else:
            rec = df_mes[df_mes['tipo']=='Receita']['valor'].sum()
            desp = df_mes[df_mes['tipo']=='Despesa']['valor'].sum()
            inv = df_mes[df_mes['tipo']=='Investimento']['valor'].sum()
            sobra = rec - desp - inv
            
            # --- KPI ---
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Receita Líquida", f"R$ {rec:,.2f}")
            k2.metric("Despesas Totais", f"R$ {desp:,.2f}", delta=-desp, delta_color="inverse")
            k3.metric("Total Investido", f"R$ {inv:,.2f}", delta=inv)
            k4.metric("Caixa Livre", f"R$ {sobra:,.2f}", 
                      delta_color="off" if sobra >= 0 else "inverse")
            
            st.divider()

            c1, c2 = st.columns([1.5, 1])
            
            # GRÁFICO 1: WATERFALL (Fluxo Correto)
            with c1:
                st.subheader("1. Fluxo de Caixa (Waterfall)")
                cats = df_mes[df_mes['tipo'].isin(['Despesa', 'Investimento'])]['categoria'].tolist()
                vals = [-x for x in df_mes[df_mes['tipo'].isin(['Despesa', 'Investimento'])]['valor'].tolist()]
                
                fig_water = go.Figure(go.Waterfall(
                    measure = ["relative"] * (len(vals) + 1) + ["total"],
                    x = ["Entrada"] + cats + ["Sobra"],
                    y = [rec] + vals + [sobra],
                    connector = {"line": {"color": "gray"}},
                    decreasing = {"marker": {"color": "#ef553b"}},
                    increasing = {"marker": {"color": "#00cc96"}},
                    totals = {"marker": {"color": "white"}}
                ))
                fig_water.update_layout(height=400, template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_water, use_container_width=True)
            
            # GRÁFICO 2: GAUGE (Taxa de Poupança)
            with c2:
                st.subheader("2. Taxa de Investimento")
                taxa = (inv / rec * 100) if rec > 0 else 0
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number", value = taxa,
                    title = {'text': "% da Renda Investida"},
                    gauge = {
                        'axis': {'range': [0, 50]}, # Meta de 50%
                        'bar': {'color': "#238636"},
                        'steps': [{'range': [0, 10], 'color': "#8c1b1b"}, {'range': [10, 30], 'color': "#d4a72c"}]
                    }
                ))
                fig_gauge.update_layout(height=350, template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_gauge, use_container_width=True)

            # GRÁFICO 3: SUNBURST (Detalhamento de Gastos)
            st.subheader("3. Raio-X das Despesas")
            df_desp = df_mes[df_mes['tipo']=='Despesa']
            if not df_desp.empty:
                fig_sun = px.sunburst(df_desp, path=['tipo', 'categoria'], values='valor', color='valor', color_continuous_scale='Reds')
                fig_sun.update_layout(height=400, template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_sun, use_container_width=True)

    # ==========================================================================
    # ABA 3: VISÃO ANUAL (GRÁFICOS 4, 5, 6, 7, 8)
    # ==========================================================================
    elif menu == "📈 Visão Anual":
        st.title(f"Inteligência Estratégica: {sel_ano}")
        
        if df_ano.empty:
            st.info("Preencha mais meses para gerar inteligência.")
        else:
            # PREPARAÇÃO DOS DADOS ANUAIS
            pivot = df_ano.pivot_table(index='mes_ano', columns='tipo', values='valor', aggfunc='sum', fill_value=0)
            if 'Investimento' not in pivot: pivot['Investimento'] = 0
            if 'Receita' not in pivot: pivot['Receita'] = 0
            if 'Despesa' not in pivot: pivot['Despesa'] = 0
            
            pivot['Patrimonio_Total'] = pivot['Investimento'].cumsum()
            
            c1, c2 = st.columns(2)
            
            # GRÁFICO 4: EVOLUÇÃO PATRIMONIAL (LINHA)
            with c1:
                st.subheader("4. Crescimento de Patrimônio")
                fig_line = px.line(pivot, x=pivot.index, y='Patrimonio_Total', markers=True)
                fig_line.update_traces(line_color='#00cc96', line_width=4, fill='tozeroy')
                fig_line.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_line, use_container_width=True)
                
            # GRÁFICO 5: BARRAS AGRUPADAS
            with c2:
                st.subheader("5. Entradas vs Saídas")
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(x=pivot.index, y=pivot['Receita'], name='Ganho', marker_color='#1f6feb'))
                fig_bar.add_trace(go.Bar(x=pivot.index, y=pivot['Despesa'], name='Gasto', marker_color='#d23430'))
                fig_bar.add_trace(go.Bar(x=pivot.index, y=pivot['Investimento'], name='Investido', marker_color='#238636'))
                fig_bar.update_layout(barmode='group', template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_bar, use_container_width=True)
                
            # GRÁFICO 6: HEATMAP (SAZONALIDADE)
            st.subheader("6. Mapa de Calor de Gastos")
            df_desp_ano = df_ano[df_ano['tipo']=='Despesa']
            if not df_desp_ano.empty:
                heat_data = df_desp_ano.pivot_table(index='categoria', columns='mes_ano', values='valor', aggfunc='sum', fill_value=0)
                fig_heat = px.imshow(heat_data, color_continuous_scale='Magma', text_auto=True)
                fig_heat.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', height=500)
                st.plotly_chart(fig_heat, use_container_width=True)
                
            c3, c4 = st.columns(2)
            
            # GRÁFICO 7: RANKING DE CUSTOS
            with c3:
                st.subheader("7. Onde gastei mais no ano?")
                ranking = df_desp_ano.groupby('categoria')['valor'].sum().sort_values()
                fig_rank = px.bar(ranking, x='valor', y=ranking.index, orientation='h', color='valor')
                fig_rank.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_rank, use_container_width=True)
                
            # GRÁFICO 8: COMPOSIÇÃO DE INVESTIMENTOS
            with c4:
                st.subheader("8. Minha Carteira Anual")
                df_inv_ano = df_ano[df_ano['tipo']=='Investimento']
                if not df_inv_ano.empty:
                    fig_pie = px.pie(df_inv_ano, values='valor', names='categoria', hole=0.5)
                    fig_pie.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_pie, use_container_width=True)

    # ==========================================================================
    # ABA 4: CONFIGURAÇÕES
    # ==========================================================================
    elif menu == "⚙️ Configurações":
        st.header("Gerenciar Categorias")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            if n := st.text_input("Nova Receita"):
                if st.button("Add Rec"): db.add_categoria(user, 'Receita', n); st.rerun()
        with c2:
            if n := st.text_input("Novo Investimento"):
                if st.button("Add Inv"): db.add_categoria(user, 'Investimento', n); st.rerun()
        with c3:
            if n := st.text_input("Nova Despesa"):
                if st.button("Add Desp"): db.add_categoria(user, 'Despesa', n); st.rerun()

# --- INIT ---
if 'user' not in st.session_state: st.session_state['user'] = None
if st.session_state['user']: main_app()
else: login_screen()