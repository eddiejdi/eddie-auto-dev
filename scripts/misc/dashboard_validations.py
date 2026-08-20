#!/usr/bin/env python3
"""
Dashboard de Validações - Streamlit
Visualiza histórico de validações da landing page
"""

import json
import sys
from pathlib import Path

try:
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
    import streamlit as st
except ImportError:
    print("❌ Dependências não instaladas: pip install streamlit pandas plotly")
    sys.exit(1)


class ValidationDashboard:
    """Dashboard de validações"""
    
    def __init__(self, history_file="/tmp/validation_logs/validation_history.json"):
        self.history_file = Path(history_file)
        
    def load_history(self):
        """Carrega histórico de validações"""
        if not self.history_file.exists():
            return []
        
        try:
            with open(self.history_file) as f:
                return json.load(f)
        except:
            return []
    
    def parse_data(self):
        """Parse dos dados para DataFrame"""
        history = self.load_history()
        
        if not history:
            return None
        
        data = []
        for entry in history:
            data.append({
                "timestamp": pd.to_datetime(entry["timestamp"]),
                "status": entry["status"],
                "total": entry.get("stats", {}).get("total", 0),
                "success": entry.get("stats", {}).get("success", 0),
                "failed": entry.get("stats", {}).get("failed", 0),
            })
        
        return pd.DataFrame(data)
    
    def render(self):
        """Render do dashboard"""
        
        st.set_page_config(
            page_title="RPA4ALL - Validação de Links",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        st.title("📊 Dashboard de Validações - Landing Page RPA4ALL")
        
        # Carregar dados
        df = self.parse_data()
        
        if df is None or df.empty:
            st.warning("⚠️  Nenhum dado de validação encontrado")
            st.info("Execute: `python3 validation_scheduler.py https://www.rpa4all.com/`")
            return
        
        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            success_count = (df["status"] == "success").sum()
            st.metric("✅ Sucessos", success_count)
        
        with col2:
            error_count = (df["status"] == "error").sum()
            st.metric("❌ Erros", error_count)
        
        with col3:
            total_tests = len(df)
            st.metric("📊 Total Testes", total_tests)
        
        with col4:
            if total_tests > 0:
                success_rate = (success_count / total_tests) * 100
                st.metric("📈 Taxa Sucesso", f"{success_rate:.1f}%")
        
        # Gráficos
        st.header("📈 Análise de Tendências")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Timeline de status
            fig1 = px.scatter(
                df.sort_values("timestamp"),
                x="timestamp",
                y="status",
                color="status",
                title="Timeline de Status",
                hover_data=["total", "failed"]
            )
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            # Evolução de links
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=df["timestamp"],
                y=df["success"],
                name="✅ OK",
                mode="lines+markers"
            ))
            fig2.add_trace(go.Scatter(
                x=df["timestamp"],
                y=df["failed"],
                name="❌ Problemas",
                mode="lines+markers"
            ))
            fig2.update_layout(
                title="Evolução de Links",
                xaxis_title="Data",
                yaxis_title="Quantidade",
                hovermode="x unified"
            )
            st.plotly_chart(fig2, use_container_width=True)
        
        # Tabela detalhada
        st.header("📋 Detalhes de Validações")
        
        display_df = df.copy()
        display_df["timestamp"] = display_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        display_df["success_rate"] = ((display_df["success"] / display_df["total"]) * 100).round(1)
        
        display_df = display_df[["timestamp", "status", "total", "success", "failed", "success_rate"]]
        display_df.columns = ["Data/Hora", "Status", "Total Links", "OK", "Problemas", "Taxa OK %"]
        
        st.dataframe(display_df, use_container_width=True)
        
        # Alertas recentes
        st.header("⚠️  Alertas Recentes")
        
        errors = df[df["status"] != "success"].tail(5)
        if not errors.empty:
            for idx, row in errors.iterrows():
                with st.expander(f"🔴 {row['timestamp'].strftime('%Y-%m-%d %H:%M')} - {row['status']}"):
                    st.write(f"Total: {row['total']} | OK: {row['success']} | Problemas: {row['failed']}")
        else:
            st.success("✅ Nenhum erro nos últimos testes!")
        
        # Instruções
        st.sidebar.header("📖 Instruções")
        st.sidebar.markdown("""
        ### Como usar:
        
        1. **Executar validação manual:**
        ```bash
        python3 validation_scheduler.py https://www.rpa4all.com/
        ```
        
        2. **Visualizar relatório:**
        ```bash
        python3 validation_scheduler.py summary
        ```
        
        3. **Configurar alertas Telegram:**
        ```bash
        python3 setup_telegram_alerts.py setup
        ```
        
        4. **Instalar cron job:**
        ```bash
        bash setup_validation_cron.sh
        ```
        
        ### Logs:
        - Histórico: `/tmp/validation_logs/validation_history.json`
        - Cron logs: `/var/log/rpa4all-validation/`
        """)


def main():
    """Entry point"""
    dashboard = ValidationDashboard()
    dashboard.render()


if __name__ == "__main__":
    main()
