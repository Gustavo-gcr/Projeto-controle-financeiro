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
# 1. CONFIGURAÇÃO DA PÁGINA & ESTILO
# ==============================================================================
st.set_page_config(
    page_title="Gustavo Financial Suite",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="expanded"
)

# Estilo CSS para visual Dark/Executive
st.markdown("""
    <style>
    .stApp {
        background-color: #0E1117;
    }
    .stMetric {
        background-color: #1A1C24;
        border: 1px solid #41444C;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    div[data-testid="stExpander"] {
        background-color: #1A1C24;
        border: 1px solid #41444C;
        border-radius: 8px;
    }
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONTROLLER DO FIREBASE (SINGLETON)
# ==============================================================================
class FirebaseManager:
    """Gerencia a conexão e operações com o Firestore de forma segura."""
    
    def __init__(self):
        # Evita erro de inicialização múltipla do Firebase
        if not firebase_admin._apps:
            try:
                # Carrega do secrets.toml
                cred_dict = dict(st.secrets["firebase"])
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
            except Exception as e:
                st.error(f"❌ Erro Crítico de Conexão: {e}")
                st.stop()
        self.db = firestore.client()

    def verificar_permissao(self, email):
        """Verifica se o e-mail existe na coleção 'usuarios' (Whitelist)."""
        if not email: return False
        try:
            doc = self.db.collection('usuarios').document(email.strip().lower()).get()
            return doc.exists
        except:
            return False

    def inicializar_usuario(self, email):
        """Cria templates padrão se o usuário for novo."""
        doc_ref = self.db.collection('usuarios').document(email)
        doc = doc_ref.get()
        
        dados_padrao = {
            'cat_receita': ['Salário', 'Investimentos', 'Extras'],
            'cat_despesa': ['Moradia', 'Alimentação', 'Transporte', 'Lazer', 'Cartão de Crédito'],
            'meta_mensal': 0.0
        }
        
        if not doc.exists:
            # Se não existe, cria
            doc_ref.set(dados_padrao)
            return dados_padrao
        
        dados = doc.to_dict()
        # Garante que as chaves existam mesmo se o doc for antigo
        if 'cat_receita' not in dados:
            doc_ref.set(dados_padrao, merge=True)
            return dados_padrao
        return dados

    def add_categoria(self, email, tipo, nova_cat):
        """Adiciona nova categoria ao template do usuário."""
        key = 'cat_receita' if tipo == 'Receita' else 'cat_despesa'
        self.db.collection('usuarios').document(email).update({
            key: firestore.ArrayUnion([nova_cat])
        })

    def salvar_transacao(self, email, mes_ano, categoria, tipo, valor):
        """Salva ou atualiza transação (ID único = email_mes_categoria)."""
        clean_cat = categoria.replace(" ", "_").lower()
        doc_id = f"{email}_{mes_ano}_{clean_cat}"
        
        payload = {
            'email': email,
            'mes_ano': mes_ano,
            'categoria': categoria,
            'tipo': tipo,
            'valor': float(valor),
            'timestamp': firestore.SERVER_TIMESTAMP
        }
        self.db.collection('lancamentos').document(doc_id).set(payload)

    def buscar_dados(self, email, mes_ano=None):
        """Retorna DataFrame com os dados."""
        ref = self.db.collection('lancamentos')
        query = ref.where('email', '==', email)
        if mes_ano:
            query = query.where('mes_ano', '==', mes_ano)
            
        docs = query.stream()
        data = [d.to_dict() for d in docs]
        return pd.DataFrame(data)

# Instancia o banco
fb = FirebaseManager()

# ==============================================================================
# 3. COMPONENTES VISUAIS E GRÁFICOS
# ==============================================================================
def plot_sankey(df):
    """Diagrama de Fluxo: Receita -> Saldo/Despesas -> Categorias"""
    if df.empty: return go.Figure()

    receitas = df[df['tipo'] == 'Receita']
    despesas = df[df['tipo'] == 'Despesa']
    
    total_rec = receitas['valor'].sum()
    total_desp = despesas['valor'].sum()
    saldo = total_rec - total_desp
    
    # Nós: [0: Receita Total, 1..N: Categorias Despesa, N+1: Saldo]
    cats_despesa = despesas['categoria'].unique().tolist()
    labels = ["Renda Bruta"] + cats_despesa + (["Saldo Acumulado"] if saldo > 0 else [])
    
    label_idx = {l: i for i, l in enumerate(labels)}
    
    sources, targets, values, colors = [], [], [], []
    
    # Links: Renda -> Categorias
    for cat in cats_despesa:
        val = despesas[despesas['categoria']==cat]['valor'].sum()
        if val > 0:
            sources.append(label_idx["Renda Bruta"])
            targets.append(label_idx[cat])
            values.append(val)
            colors.append("rgba(255, 100, 100, 0.4)") # Vermelho suave
            
    # Link: Renda -> Saldo
    if saldo > 0:
        sources.append(label_idx["Renda Bruta"])
        targets.append(label_idx["Saldo Acumulado"])
        values.append(saldo)
        colors.append("rgba(100, 255, 150, 0.4)") # Verde suave
        
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15, thickness=20, line=dict(color="black", width=0.5),
            label=labels, color="#4B90F5"
        ),
        link=dict(source=sources, target=targets, value=values, color=colors)
    )])
    fig.update_layout(title="Fluxo do Dinheiro", height=400, margin=dict(l=0,r=0,t=40,b=0))
    return fig

def plot_waterfall(receita, despesa, saldo):
    """Gráfico Cascata: Mostra como o salário é consumido."""
    fig = go.Figure(go.Waterfall(
        name = "20", orientation = "v",
        measure = ["relative", "relative", "total"],
        x = ["Receita", "Despesas", "Saldo Final"],
        textposition = "outside",
        text = [f"{receita/1000:.1f}k", f"-{despesa/1000:.1f}k", f"{saldo/1000:.1f}k"],
        y = [receita, -despesa, saldo],
        connector = {"line": {"color": "rgb(63, 63, 63)"}},
    ))
    fig.update_layout(title="Balanço Líquido", height=400)
    return fig

# ==============================================================================
# 4. LÓGICA PRINCIPAL (MAIN)
# ==============================================================================
def main():
    # --- TELA DE LOGIN ---
    if 'user' not in st.session_state:
        c1, c2, c3 = st.columns([1, 1.5, 1])
        with c2:
            st.title("🔒 Acesso Restrito")
            with st.form("login_form"):
                email = st.text_input("E-mail Cadastrado").strip().lower()
                btn = st.form_submit_button("Entrar", use_container_width=True)
                
                if btn:
                    if fb.verificar_permissao(email):
                        st.session_state['user'] = email
                        st.toast(f"Bem-vindo, {email}", icon="✅")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Usuário não autorizado no banco de dados.")
        return # Para a execução aqui se não estiver logado

    # --- USUÁRIO LOGADO ---
    user_email = st.session_state['user']
    
    # Sidebar
    with st.sidebar:
        st.markdown(f"### 👤 {user_email.split('@')[0].title()}")
        if st.button("Sair"):
            del st.session_state['user']
            st.rerun()
        
        st.divider()
        st.header("🗓️ Período")
        
        # Seletores de Data
        ano_atual = datetime.now().year
        mes_atual = datetime.now().month
        anos = [ano_atual-1, ano_atual, ano_atual+1]
        meses = {i: m for i, m in enumerate(calendar.month_name) if i > 0}
        
        sel_ano = st.selectbox("Ano", anos, index=1)
        sel_mes = st.selectbox("Mês", list(meses.values()), index=mes_atual-1)
        
        # Chave "YYYY-MM" para o banco
        sel_mes_num = list(meses.keys())[list(meses.values()).index(sel_mes)]
        mes_chave = f"{sel_ano}-{sel_mes_num:02d}"
        
        st.info(f"Editando: **{mes_chave}**")

    # Carrega configurações e dados
    config = fb.inicializar_usuario(user_email)
    df_mes = fb.buscar_dados(user_email, mes_chave)
    
    # Mapa rápido para inputs (Categoria -> Valor)
    mapa_val = {row['categoria']: row['valor'] for _, row in df_mes.iterrows()} if not df_mes.empty else {}

    # ABAS
    tab_dash, tab_gestao, tab_config = st.tabs(["📊 Dashboard Analítico", "📝 Gestão de Caixa", "⚙️ Configurações"])

    # --- ABA GESTÃO ---
    with tab_gestao:
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("Entradas (Receitas)")
            with st.container(border=True):
                tot_rec = 0
                for cat in config['cat_receita']:
                    val_db = mapa_val.get(cat, 0.0)
                    val = st.number_input(f"💰 {cat}", value=val_db, min_value=0.0, step=100.0, key=f"in_{cat}")
                    if val != val_db:
                        fb.salvar_transacao(user_email, mes_chave, cat, 'Receita', val)
                    tot_rec += val
                st.markdown(f"**Total Entradas:** :green[R$ {tot_rec:,.2f}]")

        with c2:
            st.subheader("Saídas (Despesas)")
            with st.container(border=True):
                tot_desp = 0
                for cat in config['cat_despesa']:
                    val_db = mapa_val.get(cat, 0.0)
                    val = st.number_input(f"💸 {cat}", value=val_db, min_value=0.0, step=50.0, key=f"out_{cat}")
                    if val != val_db:
                        fb.salvar_transacao(user_email, mes_chave, cat, 'Despesa', val)
                    tot_desp += val
                st.markdown(f"**Total Saídas:** :red[R$ {tot_desp:,.2f}]")

    # --- ABA DASHBOARD ---
    with tab_dash:
        # Recarrega dados atualizados
        df_dash = fb.buscar_dados(user_email, mes_chave)
        
        if df_dash.empty:
            st.warning("Sem dados para este mês. Vá em 'Gestão de Caixa' para começar.")
        else:
            rec = df_dash[df_dash['tipo']=='Receita']['valor'].sum()
            desp = df_dash[df_dash['tipo']=='Despesa']['valor'].sum()
            saldo = rec - desp
            
            # KPIs
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Receita", f"R$ {rec:,.2f}")
            k2.metric("Despesas", f"R$ {desp:,.2f}", delta=-desp, delta_color="inverse")
            k3.metric("Saldo", f"R$ {saldo:,.2f}", delta=saldo)
            if rec > 0:
                poupanca = (saldo/rec)*100
                k4.metric("Taxa de Poupança", f"{poupanca:.1f}%")
            
            st.divider()
            
            # Gráficos
            g1, g2 = st.columns([1.5, 1])
            with g1:
                st.plotly_chart(plot_sankey(df_dash), use_container_width=True)
            with g2:
                st.plotly_chart(plot_waterfall(rec, desp, saldo), use_container_width=True)
                
            # Gráfico de Rosca
            st.subheader("Detalhamento de Gastos")
            df_pie = df_dash[df_dash['tipo']=='Despesa']
            if not df_pie.empty:
                fig_pie = px.pie(df_pie, values='valor', names='categoria', hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)

    # --- ABA CONFIGURAÇÕES ---
    with tab_config:
        st.markdown("### Personalizar Categorias")
        st.info("O que você adicionar aqui aparecerá na aba Gestão para todos os meses.")
        
        cc1, cc2 = st.columns(2)
        with cc1:
            new_rec = st.text_input("Nova Receita (ex: Freelance)")
            if st.button("Adicionar Receita"):
                fb.add_categoria(user_email, 'Receita', new_rec)
                st.success("Adicionado! Atualize a página.")
                
        with cc2:
            new_desp = st.text_input("Nova Despesa (ex: Academia)")
            if st.button("Adicionar Despesa"):
                fb.add_categoria(user_email, 'Despesa', new_desp)
                st.success("Adicionado! Atualize a página.")

if __name__ == "__main__":
    main()