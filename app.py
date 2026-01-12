import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import time

# ==============================================================================
# 1. CONFIGURAÇÃO VISUAL E CSS (UI/UX)
# ==============================================================================
st.set_page_config(
    page_title="Gestão Financeira Pro",
    layout="wide",
    page_icon="💳",
    initial_sidebar_state="expanded"
)

# Tema Dark Moderno com CSS Injetado
st.markdown("""
    <style>
    /* Fundo geral e fontes */
    .stApp {
        background-color: #0e1117;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }
    
    /* Cards de Métricas */
    div[data-testid="metric-container"] {
        background-color: #21262d;
        border: 1px solid #30363d;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    }
    
    /* Inputs numéricos mais bonitos */
    .stNumberInput input {
        background-color: #0d1117 !important;
        color: white !important;
        border: 1px solid #30363d !important;
        border-radius: 5px;
    }
    
    /* Títulos e textos */
    h1, h2, h3 {
        color: #f0f6fc !important;
        font-family: 'Segoe UI', sans-serif;
    }
    
    /* Separadores */
    hr {
        border-color: #30363d;
    }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. SISTEMA DE DADOS (BACKEND)
# ==============================================================================

# Dicionário de Tradução para garantir PT-BR
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
                st.error(f"Erro de conexão: {e}")
                st.stop()
        self.db = firestore.client()

    def verificar_usuario(self, email):
        if not email: return False
        try:
            doc = self.db.collection('usuarios').document(email.strip().lower()).get()
            return doc.exists
        except: return False

    def pegar_config(self, email):
        """Busca categorias. Se não existir, cria padrão."""
        doc_ref = self.db.collection('usuarios').document(email)
        doc = doc_ref.get()
        padrao = {
            'receitas': ['Salário', 'Investimentos', 'Extras'],
            'despesas': ['Aluguel/Condomínio', 'Mercado', 'Lazer', 'Cartão de Crédito', 'Transporte', 'Assinaturas']
        }
        
        if not doc.exists:
            doc_ref.set(padrao)
            return padrao
        
        dados = doc.to_dict()
        # Garante estrutura mesmo em docs antigos
        if 'receitas' not in dados:
            doc_ref.set(padrao, merge=True)
            return padrao
        return dados

    def salvar_transacao(self, email, mes_ano, categoria, tipo, valor):
        """Salva com ID único composto: email_mes_categoria"""
        clean_cat = categoria.replace(" ", "_").lower()
        doc_id = f"{email}_{mes_ano}_{clean_cat}"
        
        payload = {
            'email': email,
            'mes_ano': mes_ano, # Formato YYYY-MM
            'categoria': categoria,
            'tipo': tipo,
            'valor': float(valor),
            'timestamp': firestore.SERVER_TIMESTAMP
        }
        self.db.collection('lancamentos').document(doc_id).set(payload)

    def buscar_mes(self, email, mes_ano):
        """Retorna DF apenas do mês selecionado"""
        ref = self.db.collection('lancamentos')
        query = ref.where('email', '==', email).where('mes_ano', '==', mes_ano)
        docs = query.stream()
        return pd.DataFrame([d.to_dict() for d in docs])

    def buscar_ano_inteiro(self, email, ano):
        """Busca tudo que começa com o Ano (ex: 2026-*)"""
        # Firestore não tem 'startswith' nativo fácil, então pegamos intervalo
        start = f"{ano}-01"
        end = f"{ano}-12"
        
        ref = self.db.collection('lancamentos')
        query = ref.where('email', '==', email).where('mes_ano', '>=', start).where('mes_ano', '<=', end)
        docs = query.stream()
        return pd.DataFrame([d.to_dict() for d in docs])

    def add_categoria(self, email, tipo, nova_cat):
        key = 'receitas' if tipo == 'Receita' else 'despesas'
        self.db.collection('usuarios').document(email).update({
            key: firestore.ArrayUnion([nova_cat])
        })

db = BancoDeDados()

# ==============================================================================
# 3. INTERFACE (FRONTEND)
# ==============================================================================

def login_screen():
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<br><br><h1 style='text-align: center;'>🔐 Acesso Restrito</h1>", unsafe_allow_html=True)
        with st.form("login"):
            email = st.text_input("E-mail Cadastrado").strip().lower()
            if st.form_submit_button("ENTRAR", use_container_width=True):
                if db.verificar_usuario(email):
                    st.session_state['user'] = email
                    st.rerun()
                else:
                    st.error("Usuário não encontrado.")

def main_app():
    user = st.session_state['user']
    
    # --- BARRA LATERAL (NAVEGAÇÃO COMPLETA) ---
    with st.sidebar:
        st.title(f"Olá, {user.split('@')[0].title()}")
        st.markdown("---")
        
        # 1. Seletor de Data
        st.header("📅 Período")
        ano_atual = datetime.now().year
        sel_ano = st.selectbox("Ano", [ano_atual-1, ano_atual, ano_atual+1], index=1)
        
        # Mapa reverso para pegar o número do mês pelo nome em PT
        nomes_meses = list(MAPA_MESES.values())
        mes_atual_idx = datetime.now().month - 1
        sel_mes_nome = st.selectbox("Mês", nomes_meses, index=mes_atual_idx)
        
        # Converter para YYYY-MM (Ex: 2026-02)
        mes_num = [k for k, v in MAPA_MESES.items() if v == sel_mes_nome][0]
        mes_chave = f"{sel_ano}-{mes_num:02d}"
        
        st.caption(f"Editando dados de: **{sel_mes_nome}/{sel_ano}**")
        st.markdown("---")
        
        # 2. Menu Principal
        menu = st.radio(
            "Navegação", 
            ["📊 Visão Mensal", "💰 Lançamentos", "📈 Visão Anual", "⚙️ Configurações"]
        )
        
        st.markdown("---")
        if st.button("Sair"):
            st.session_state['user'] = None
            st.rerun()

    # --- CARREGAR DADOS ---
    config = db.pegar_config(user)
    df_mes = db.buscar_mes(user, mes_chave)
    
    # Criar dicionário de valores existentes para preencher inputs
    # Se não tiver dado no banco, retorna 0.0
    val_map = {row['categoria']: row['valor'] for _, row in df_mes.iterrows()} if not df_mes.empty else {}

    # --- PÁGINA: LANÇAMENTOS ---
    if menu == "💰 Lançamentos":
        st.title(f"Lançamentos: {sel_mes_nome} de {sel_ano}")
        st.markdown("Altere os valores abaixo. **O salvamento é automático ao sair do campo.**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📥 Receitas (Entradas)")
            with st.container():
                total_rec = 0.0
                for cat in config['receitas']:
                    # O SEGREDO DO BUG: O 'key' precisa ter o 'mes_chave'
                    # Assim, quando muda o mês, o Streamlit reseta o input
                    unique_key = f"in_{mes_chave}_{cat}"
                    valor_atual = val_map.get(cat, 0.0)
                    
                    novo_val = st.number_input(
                        f"{cat}", 
                        value=float(valor_atual), 
                        min_value=0.0, 
                        step=50.0,
                        key=unique_key
                    )
                    
                    if novo_val != valor_atual:
                        db.salvar_transacao(user, mes_chave, cat, 'Receita', novo_val)
                    
                    total_rec += novo_val
                st.success(f"Total Receitas: R$ {total_rec:,.2f}")

        with col2:
            st.subheader("📤 Despesas (Saídas)")
            with st.container():
                total_desp = 0.0
                for cat in config['despesas']:
                    unique_key = f"out_{mes_chave}_{cat}"
                    valor_atual = val_map.get(cat, 0.0)
                    
                    novo_val = st.number_input(
                        f"{cat}", 
                        value=float(valor_atual), 
                        min_value=0.0, 
                        step=50.0,
                        key=unique_key
                    )
                    
                    if novo_val != valor_atual:
                        db.salvar_transacao(user, mes_chave, cat, 'Despesa', novo_val)
                    
                    total_desp += novo_val
                st.error(f"Total Despesas: R$ {total_desp:,.2f}")

    # --- PÁGINA: VISÃO MENSAL ---
    elif menu == "📊 Visão Mensal":
        st.title(f"Dashboard: {sel_mes_nome}/{sel_ano}")
        
        if df_mes.empty:
            st.info("Nenhum dado lançado neste mês. Vá na aba 'Lançamentos'.")
        else:
            rec = df_mes[df_mes['tipo']=='Receita']['valor'].sum()
            desp = df_mes[df_mes['tipo']=='Despesa']['valor'].sum()
            saldo = rec - desp
            
            # 1. KPIs
            k1, k2, k3 = st.columns(3)
            k1.metric("Receita Total", f"R$ {rec:,.2f}")
            k2.metric("Despesa Total", f"R$ {desp:,.2f}", delta=-desp, delta_color="inverse")
            k3.metric("Saldo em Caixa", f"R$ {saldo:,.2f}", delta=saldo)
            
            st.divider()
            
            # 2. Gráficos
            g1, g2 = st.columns([1, 2])
            
            with g1:
                st.subheader("Para onde foi o dinheiro?")
                df_desp = df_mes[df_mes['tipo']=='Despesa']
                if not df_desp.empty:
                    # Gráfico de Rosca (Donut) mais elegante
                    fig = px.pie(df_desp, values='valor', names='categoria', hole=0.6, 
                                 color_discrete_sequence=px.colors.sequential.RdBu)
                    fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.caption("Sem despesas cadastradas.")
            
            with g2:
                st.subheader("Balanço Visual")
                # Gráfico de Barras Horizontal
                df_bar = df_mes.groupby('tipo')['valor'].sum().reset_index()
                fig_bar = px.bar(df_bar, x='valor', y='tipo', orientation='h', 
                                 color='tipo', color_discrete_map={'Receita':'#00cc96', 'Despesa':'#ef553b'},
                                 text_auto='.2s')
                fig_bar.update_layout(height=250, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_bar, use_container_width=True)

    # --- PÁGINA: VISÃO ANUAL (NOVA) ---
    elif menu == "📈 Visão Anual":
        st.title(f"Relatório Anual - {sel_ano}")
        
        df_ano = db.buscar_ano_inteiro(user, sel_ano)
        
        if df_ano.empty:
            st.warning(f"Não há registros em {sel_ano} ainda.")
        else:
            # Agregação por Mês e Tipo
            df_agg = df_ano.groupby(['mes_ano', 'tipo'])['valor'].sum().reset_index().sort_values('mes_ano')
            
            # Gráfico de Evolução (Linha/Area)
            st.subheader("Evolução Financeira")
            fig_area = px.area(df_agg, x='mes_ano', y='valor', color='tipo', 
                               color_discrete_map={'Receita':'#00cc96', 'Despesa':'#ef553b'},
                               markers=True)
            fig_area.update_layout(xaxis_title="Mês", yaxis_title="Valor (R$)")
            st.plotly_chart(fig_area, use_container_width=True)
            
            st.divider()
            
            # Tabela Resumo (Pivot Table)
            st.subheader("Extrato Detalhado do Ano")
            pivot = df_ano.pivot_table(index='categoria', columns='mes_ano', values='valor', aggfunc='sum', fill_value=0)
            # Adiciona coluna de Total
            pivot['TOTAL ANUAL'] = pivot.sum(axis=1)
            # Formatação
            st.dataframe(pivot.style.format("R$ {:,.2f}"), use_container_width=True, height=400)

    # --- PÁGINA: CONFIGURAÇÕES ---
    elif menu == "⚙️ Configurações":
        st.title("Configurações do Sistema")
        
        c1, c2 = st.columns(2)
        with c1:
            st.info("Adicionar Fonte de Receita")
            nova_rec = st.text_input("Nome da nova receita")
            if st.button("Adicionar Receita"):
                db.add_categoria(user, 'Receita', nova_rec)
                st.success("Adicionado! Atualize a página.")
        
        with c2:
            st.info("Adicionar Tipo de Despesa")
            nova_desp = st.text_input("Nome da nova despesa")
            if st.button("Adicionar Despesa"):
                db.add_categoria(user, 'Despesa', nova_desp)
                st.success("Adicionado! Atualize a página.")

# --- ROTEAMENTO ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

if st.session_state['user']:
    main_app()
else:
    login_screen()