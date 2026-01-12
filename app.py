import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import calendar

# ==============================================================================
# 1. CONFIGURAÇÃO VISUAL (UI/UX PREMIUM)
# ==============================================================================
st.set_page_config(
    page_title="Sistema Financeiro Gustavo",
    layout="wide",
    page_icon="🏦",
    initial_sidebar_state="expanded"
)

# CSS PROFISSIONAL PARA APARÊNCIA "APP NATIVO"
st.markdown("""
    <style>
    /* Fundo Dark Moderno */
    .stApp { background-color: #0e1117; }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }
    
    /* Métricas (Cards) */
    div[data-testid="metric-container"] {
        background-color: #1f242d;
        border-left: 5px solid #30363d;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
    }
    
    /* Abas customizadas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #161b22;
        border-radius: 4px;
        color: #fff;
    }
    .stTabs [aria-selected="true"] {
        background-color: #238636;
        color: white;
    }
    
    /* Títulos e textos */
    h1, h2, h3 { color: #e6edf3 !important; font-family: 'Inter', sans-serif; }
    p, label { color: #c9d1d9 !important; }
    
    /* Inputs */
    .stNumberInput input { background-color: #0d1117 !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. MOTOR DE DADOS (CORREÇÃO DE ERROS E NOVA LÓGICA)
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
                st.error(f"Erro Crítico de Conexão: {e}")
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
        # Nova estrutura com INVESTIMENTOS separado
        padrao = {
            'receitas': ['Salário', 'Freelance'],
            'despesas': ['Aluguel', 'Mercado', 'Lazer', 'Cartão'],
            'investimentos': ['Poupança', 'CDB', 'Ações', 'Reserva']
        }
        
        if not doc.exists:
            doc_ref.set(padrao)
            return padrao
        
        dados = doc.to_dict()
        # Garante que a chave 'investimentos' exista (migração automática)
        if 'investimentos' not in dados:
            doc_ref.update({'investimentos': padrao['investimentos']})
            dados['investimentos'] = padrao['investimentos']
        return dados

    def salvar_transacao(self, email, mes_ano, categoria, tipo, valor):
        # ID único
        doc_id = f"{email}_{mes_ano}_{categoria.replace(' ', '_').lower()}"
        payload = {
            'email': email, 'mes_ano': mes_ano, 'categoria': categoria,
            'tipo': tipo, 'valor': float(valor), 'timestamp': firestore.SERVER_TIMESTAMP
        }
        self.db.collection('lancamentos').document(doc_id).set(payload)

    def buscar_dados_gerais(self, email):
        """
        CORREÇÃO DO ERRO: Busca TUDO do usuário e filtra no Python (evita erro de índice).
        """
        ref = self.db.collection('lancamentos')
        query = ref.where('email', '==', email)
        docs = query.stream()
        lista = [d.to_dict() for d in docs]
        return pd.DataFrame(lista)

    def add_categoria(self, email, tipo, nova_cat):
        # Mapeia o tipo para a chave correta no banco
        mapa = {'Receita': 'receitas', 'Despesa': 'despesas', 'Investimento': 'investimentos'}
        key = mapa.get(tipo)
        if key:
            self.db.collection('usuarios').document(email).update({key: firestore.ArrayUnion([nova_cat])})

db = BancoDeDados()

# ==============================================================================
# 3. INTERFACE INTELIGENTE
# ==============================================================================

def login_screen():
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<br><br><h1 style='text-align: center;'>🔐 Acesso</h1>", unsafe_allow_html=True)
        with st.form("login"):
            email = st.text_input("E-mail Cadastrado").strip().lower()
            if st.form_submit_button("Entrar", use_container_width=True):
                if db.verificar_usuario(email):
                    st.session_state['user'] = email
                    st.rerun()
                else:
                    st.error("Usuário não encontrado.")

def main_app():
    user = st.session_state['user']
    
    # --- SIDEBAR FIXA ---
    with st.sidebar:
        st.title(f"👤 {user.split('@')[0].title()}")
        if st.button("Sair", use_container_width=True):
            st.session_state['user'] = None
            st.rerun()
        st.divider()
        
        st.header("🗓️ Data")
        ano_atual = datetime.now().year
        sel_ano = st.selectbox("Ano", [ano_atual-1, ano_atual, ano_atual+1], index=1)
        
        mes_atual_idx = datetime.now().month - 1
        sel_mes_nome = st.selectbox("Mês", list(MAPA_MESES.values()), index=mes_atual_idx)
        
        # Chave YYYY-MM
        mes_num = [k for k, v in MAPA_MESES.items() if v == sel_mes_nome][0]
        mes_chave = f"{sel_ano}-{mes_num:02d}"
        
        st.info(f"Visualizando: **{sel_mes_nome}/{sel_ano}**")
        
        # MENU PRINCIPAL (SIMPLES E DIRETO)
        menu = st.radio("Menu", 
            ["📝 Lançamentos", "📊 Dashboard Mensal", "📈 Visão Anual", "⚙️ Categorias"],
        )

    # Carregar Dados (Busca otimizada)
    df_full = db.buscar_dados_gerais(user)
    config = db.pegar_config(user)
    
    # Filtra dados do mês selecionado localmente
    if not df_full.empty:
        df_mes = df_full[df_full['mes_ano'] == mes_chave]
    else:
        df_mes = pd.DataFrame()
        
    val_map = {row['categoria']: row['valor'] for _, row in df_mes.iterrows()} if not df_mes.empty else {}

    # --- ABA 1: LANÇAMENTOS (3 COLUNAS) ---
    if menu == "📝 Lançamentos":
        st.header(f"Gestão de Caixa: {sel_mes_nome}")
        st.caption("Preencha os valores. O salvamento é automático ao sair do campo.")
        
        c1, c2, c3 = st.columns(3)
        
        # Coluna 1: Entradas
        with c1:
            st.subheader("🟢 Entradas")
            with st.container(border=True):
                tot_rec = 0.0
                for cat in config.get('receitas', []):
                    key_uniq = f"in_{mes_chave}_{cat}"
                    val = st.number_input(f"{cat}", value=float(val_map.get(cat, 0.0)), step=100.0, key=key_uniq)
                    if val != val_map.get(cat, 0.0): db.salvar_transacao(user, mes_chave, cat, 'Receita', val)
                    tot_rec += val
                st.metric("Total Receitas", f"R$ {tot_rec:,.2f}")

        # Coluna 2: Investimentos (NOVA LÓGICA)
        with c2:
            st.subheader("🔵 Investimentos")
            with st.container(border=True):
                tot_inv = 0.0
                for cat in config.get('investimentos', []):
                    key_uniq = f"inv_{mes_chave}_{cat}"
                    val = st.number_input(f"{cat}", value=float(val_map.get(cat, 0.0)), step=100.0, key=key_uniq)
                    if val != val_map.get(cat, 0.0): db.salvar_transacao(user, mes_chave, cat, 'Investimento', val)
                    tot_inv += val
                st.metric("Total Guardado", f"R$ {tot_inv:,.2f}")

        # Coluna 3: Despesas
        with c3:
            st.subheader("🔴 Despesas")
            with st.container(border=True):
                tot_desp = 0.0
                for cat in config.get('despesas', []):
                    key_uniq = f"out_{mes_chave}_{cat}"
                    val = st.number_input(f"{cat}", value=float(val_map.get(cat, 0.0)), step=50.0, key=key_uniq)
                    if val != val_map.get(cat, 0.0): db.salvar_transacao(user, mes_chave, cat, 'Despesa', val)
                    tot_desp += val
                st.metric("Total Gastos", f"R$ {tot_desp:,.2f}")

    # --- ABA 2: DASHBOARD MENSAL ---
    elif menu == "📊 Dashboard Mensal":
        st.header(f"Análise: {sel_mes_nome}/{sel_ano}")
        
        if df_mes.empty:
            st.warning("Preencha os lançamentos primeiro.")
        else:
            rec = df_mes[df_mes['tipo']=='Receita']['valor'].sum()
            desp = df_mes[df_mes['tipo']=='Despesa']['valor'].sum()
            inv = df_mes[df_mes['tipo']=='Investimento']['valor'].sum()
            
            # LÓGICA CORRIGIDA:
            sobra_caixa = rec - desp - inv  # O que sobrou na conta corrente
            
            # KPIs
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Ganhos", f"R$ {rec:,.2f}", border=True)
            k2.metric("Gastos", f"R$ {desp:,.2f}", delta=-desp, delta_color="inverse", border=True)
            k3.metric("Investido", f"R$ {inv:,.2f}", delta=inv, delta_color="normal", border=True)
            k4.metric("Sobra em Caixa", f"R$ {sobra_caixa:,.2f}", 
                      delta_color="off" if sobra_caixa > 0 else "inverse", 
                      help="Receita - Despesa - Investimento", border=True)
            
            st.divider()
            
            # GRÁFICO SANKEY (FLUXO DO DINHEIRO)
            st.subheader("Caminho do Dinheiro")
            st.caption("Como sua renda se divide entre Gastos, Investimentos e Sobra.")
            
            cats_desp = df_mes[df_mes['tipo']=='Despesa']['categoria'].tolist()
            vals_desp = df_mes[df_mes['tipo']=='Despesa']['valor'].tolist()
            
            cats_inv = df_mes[df_mes['tipo']=='Investimento']['categoria'].tolist()
            vals_inv = df_mes[df_mes['tipo']=='Investimento']['valor'].tolist()
            
            label = ["Receita"] + cats_desp + cats_inv + ["Sobra em Caixa"]
            source = []
            target = []
            value = []
            
            # Links Receita -> Categorias
            rec_idx = 0
            curr_idx = 1
            
            # Despesas
            for v in vals_desp:
                source.append(rec_idx); target.append(curr_idx); value.append(v); curr_idx+=1
            # Investimentos
            for v in vals_inv:
                source.append(rec_idx); target.append(curr_idx); value.append(v); curr_idx+=1
            # Sobra
            if sobra_caixa > 0:
                source.append(rec_idx); target.append(curr_idx); value.append(sobra_caixa)
                
            fig_sankey = go.Figure(data=[go.Sankey(
                node = dict(label = label, pad = 20, thickness = 20, color = "#238636"),
                link = dict(source = source, target = target, value = value)
            )])
            fig_sankey.update_layout(height=400, margin=dict(l=0,r=0,t=20,b=20), paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_sankey, use_container_width=True)

    # --- ABA 3: VISÃO ANUAL (CORRIGIDA) ---
    elif menu == "📈 Visão Anual":
        st.header(f"Panorama Anual: {sel_ano}")
        
        # Filtro Python (Evita erro do Firebase)
        if not df_full.empty:
            df_ano = df_full[df_full['mes_ano'].str.startswith(str(sel_ano))].copy()
        else:
            df_ano = pd.DataFrame()
            
        if df_ano.empty:
            st.info("Sem dados neste ano.")
        else:
            # Tabela Resumo
            df_pivot = df_ano.pivot_table(index='mes_ano', columns='tipo', values='valor', aggfunc='sum', fill_value=0)
            if 'Receita' not in df_pivot: df_pivot['Receita'] = 0
            if 'Despesa' not in df_pivot: df_pivot['Despesa'] = 0
            if 'Investimento' not in df_pivot: df_pivot['Investimento'] = 0
            
            # Evolução Patrimonial (Acumulado)
            df_pivot['Patrimonio_Mes'] = df_pivot['Investimento']
            df_pivot['Patrimonio_Acumulado'] = df_pivot['Patrimonio_Mes'].cumsum()
            
            # GRÁFICO DE EVOLUÇÃO
            st.subheader("Crescimento de Patrimônio")
            st.caption("Quanto você tem acumulado em investimentos ao longo do tempo.")
            
            fig_line = px.line(df_pivot, x=df_pivot.index, y='Patrimonio_Acumulado', markers=True)
            fig_line.update_traces(line_color='#238636', line_width=4)
            fig_line.update_layout(yaxis_title="Total Acumulado (R$)", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_line, use_container_width=True)
            
            # GRÁFICO COMPARATIVO
            st.subheader("Receita vs Despesa vs Aportes")
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(x=df_pivot.index, y=df_pivot['Receita'], name='Receita', marker_color='#2f81f7'))
            fig_bar.add_trace(go.Bar(x=df_pivot.index, y=df_pivot['Despesa'], name='Despesa', marker_color='#da3633'))
            fig_bar.add_trace(go.Bar(x=df_pivot.index, y=df_pivot['Investimento'], name='Investido', marker_color='#238636'))
            fig_bar.update_layout(barmode='group', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_bar, use_container_width=True)

    # --- ABA 4: CATEGORIAS ---
    elif menu == "⚙️ Categorias":
        st.header("Personalizar Sistema")
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

# --- EXECUÇÃO ---
if 'user' not in st.session_state: st.session_state['user'] = None
if st.session_state['user']: main_app()
else: login_screen()