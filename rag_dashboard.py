#!/usr/bin/env python3
"""
🎯 RAG AI Dashboard - Painel de Monitoramento da IA
Monitora desempenho, acurácia e métricas do sistema RAG
Inclui controle da Casa Inteligente (Home Assistant)
"""

import streamlit as st
import requests
import json
import time
from datetime import datetime, timedelta

# Configuração
RAG_API = "http://192.168.15.2:8001/api/v1"
OLLAMA_API = "http://192.168.15.2:11434/api"
HOMEASSISTANT_API = "http://localhost:8123/api"

# Carregar token do Home Assistant
def get_ha_token():
    try:
        import os
        config_path = os.path.join(os.path.dirname(__file__), "homeassistant_integration", "config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                return json.load(f).get("token", "")
    except:
        pass
    return ""

HA_TOKEN = get_ha_token()

st.set_page_config(
    page_title="🎯 RAG AI Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Customizado
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin: 10px 0;
    }
    .metric-value {
        font-size: 2.5em;
        font-weight: bold;
    }
    .metric-label {
        font-size: 0.9em;
        opacity: 0.8;
    }
    .status-online {
        color: #00ff00;
        font-weight: bold;
    }
    .status-offline {
        color: #ff0000;
        font-weight: bold;
    }
    .collection-badge {
        background: #4CAF50;
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        margin: 5px;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

def check_service(url, name):
    """Verifica se um serviço está online"""
    try:
        r = requests.get(url, timeout=5)
        return r.status_code == 200
    except:
        return False

def check_homeassistant():
    """Verifica se o Home Assistant está online"""
    try:
        headers = {"Authorization": f"Bearer {HA_TOKEN}"} if HA_TOKEN else {}
        r = requests.get(f"{HOMEASSISTANT_API}/", headers=headers, timeout=5)
        if r.status_code == 200:
            return {"status": "online", "message": r.json().get("message", "OK")}
        elif r.status_code == 401:
            return {"status": "unauthorized", "message": "Token não configurado"}
        return {"status": "error", "message": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"status": "offline", "message": str(e)}

def get_ha_states():
    """Obtém todos os estados do Home Assistant"""
    try:
        headers = {"Authorization": f"Bearer {HA_TOKEN}"}
        r = requests.get(f"{HOMEASSISTANT_API}/states", headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return []

def get_ha_config():
    """Obtém configuração do Home Assistant"""
    try:
        headers = {"Authorization": f"Bearer {HA_TOKEN}"}
        r = requests.get(f"{HOMEASSISTANT_API}/config", headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return {}

def ha_call_service(domain, service, entity_id=None, **kwargs):
    """Chama um serviço do Home Assistant"""
    try:
        headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}
        data = {"entity_id": entity_id} if entity_id else {}
        data.update(kwargs)
        r = requests.post(
            f"{HOMEASSISTANT_API}/services/{domain}/{service}",
            headers=headers,
            json=data,
            timeout=10
        )
        return r.status_code == 200
    except:
        return False

def ha_toggle(entity_id):
    """Alterna estado de um dispositivo"""
    domain = entity_id.split(".")[0]
    return ha_call_service(domain, "toggle", entity_id)

def ha_turn_on(entity_id):
    """Liga um dispositivo"""
    domain = entity_id.split(".")[0]
    return ha_call_service(domain, "turn_on", entity_id)

def ha_turn_off(entity_id):
    """Desliga um dispositivo"""
    domain = entity_id.split(".")[0]
    return ha_call_service(domain, "turn_off", entity_id)

def get_rag_stats():
    """Obtém estatísticas do RAG"""
    try:
        r = requests.get(f"{RAG_API}/rag/stats", timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def get_ollama_models():
    """Lista modelos do Ollama"""
    try:
        r = requests.get(f"{OLLAMA_API}/tags", timeout=10)
        if r.status_code == 200:
            return r.json().get('models', [])
    except:
        pass
    return []

def test_rag_search(query, collection="default"):
    """Testa uma busca no RAG"""
    try:
        start = time.time()
        r = requests.post(
            f"{RAG_API}/rag/search",
            json={"query": query, "n_results": 3, "collection": collection},
            timeout=30
        )
        latency = (time.time() - start) * 1000
        if r.status_code == 200:
            return r.json(), latency
    except:
        pass
    return None, 0

def test_ollama_inference(prompt, model="llama3.2"):
    """Testa inferência do Ollama"""
    try:
        start = time.time()
        r = requests.post(
            f"{OLLAMA_API}/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60
        )
        latency = (time.time() - start) * 1000
        if r.status_code == 200:
            return r.json(), latency
    except:
        pass
    return None, 0

# =============================================================================
# SIDEBAR
# =============================================================================
with st.sidebar:
    st.title("🎯 RAG Dashboard")
    st.markdown("---")
    
    # Status dos Serviços
    st.subheader("📡 Status dos Serviços")
    
    rag_online = check_service(f"{RAG_API.replace('/api/v1', '')}/health", "RAG")
    ollama_online = check_service(f"{OLLAMA_API}/tags", "Ollama")
    ha_status = check_homeassistant()
    ha_online = ha_status["status"] == "online"
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if rag_online:
            st.success("✅ RAG")
        else:
            st.error("❌ RAG")
    with col2:
        if ollama_online:
            st.success("✅ Ollama")
        else:
            st.error("❌ Ollama")
    with col3:
        if ha_online:
            st.success("✅ Casa")
        elif ha_status["status"] == "unauthorized":
            st.warning("⚠️ Casa")
        else:
            st.error("❌ Casa")
    
    st.markdown("---")
    
    # Navegação
    st.subheader("📊 Navegação")
    page = st.radio("", [
        "🏠 Visão Geral",
        "🏡 Casa Inteligente",
        "📚 Collections",
        "🔍 Teste de Busca",
        "🧠 Teste de Inferência",
        "📈 Benchmark"
    ])
    
    st.markdown("---")
    st.caption(f"Última atualização: {datetime.now().strftime('%H:%M:%S')}")
    if st.button("🔄 Atualizar"):
        st.rerun()

# =============================================================================
# PÁGINAS
# =============================================================================

if page == "🏠 Visão Geral":
    st.title("🏠 Visão Geral do Sistema")
    
    stats = get_rag_stats()
    
    if stats:
        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="📄 Total de Documentos",
                value=stats.get('total_documents', 0),
                delta="+26 (Bitcoin)"
            )
        
        with col2:
            st.metric(
                label="💬 Conversas Indexadas",
                value=stats.get('total_conversations', 0)
            )
        
        with col3:
            st.metric(
                label="📁 Collections",
                value=len(stats.get('collections', []))
            )
        
        with col4:
            feedback_rate = stats.get('positive_feedback_rate', 0)
            st.metric(
                label="👍 Taxa de Feedback Positivo",
                value=f"{feedback_rate:.0%}" if feedback_rate else "N/A"
            )
        
        st.markdown("---")
        
        # Collections
        st.subheader("📁 Collections Disponíveis")
        collections = stats.get('collections', [])
        
        cols = st.columns(len(collections) if collections else 1)
        for i, coll in enumerate(collections):
            with cols[i]:
                icon = "🪙" if coll == "bitcoin_knowledge" else "📚" if coll == "chat_history" else "📁"
                st.info(f"{icon} **{coll}**")
        
        # Último aprendizado
        st.markdown("---")
        st.subheader("🕐 Última Execução de Aprendizado")
        last_run = stats.get('last_learning_run', 'N/A')
        if last_run != 'N/A':
            try:
                dt = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
                st.success(f"✅ {dt.strftime('%d/%m/%Y às %H:%M:%S')}")
            except:
                st.info(last_run)
    else:
        st.error("❌ Não foi possível obter estatísticas do RAG")

elif page == "🏡 Casa Inteligente":
    st.title("🏡 Casa Inteligente")
    
    ha_status = check_homeassistant()
    
    if ha_status["status"] == "offline":
        st.error(f"❌ Home Assistant offline: {ha_status['message']}")
        st.info("""
        **Para iniciar o Home Assistant:**
        ```bash
        docker start homeassistant
        ```
        
        Ou se não estiver instalado:
        ```bash
        docker run -d --name homeassistant --restart=unless-stopped \\
            -v /home/eddie/myClaude/homeassistant/config:/config \\
            -p 8123:8123 \\
            ghcr.io/home-assistant/home-assistant:stable
        ```
        """)
    
    elif ha_status["status"] == "unauthorized":
        st.warning("⚠️ Token não configurado")
        st.info("""
        **Para configurar o Home Assistant:**
        
        1. Acesse [http://localhost:8123](http://localhost:8123)
        2. Crie sua conta de usuário
        3. Vá em **Perfil** > **Tokens de Acesso de Longa Duração**
        4. Clique em **Criar Token**
        5. Configure no terminal:
        ```bash
        cd ~/myClaude && python3 homeassistant_integration/homeassistant_api.py configure SEU_TOKEN
        ```
        """)
        
        # Campo para configurar token
        st.markdown("---")
        st.subheader("⚙️ Configurar Token")
        new_token = st.text_input("Cole seu token aqui:", type="password")
        if st.button("💾 Salvar Token"):
            if new_token:
                try:
                    import os
                    config_path = os.path.join(os.path.dirname(__file__), "homeassistant_integration", "config.json")
                    with open(config_path, 'w') as f:
                        json.dump({"url": "http://localhost:8123", "token": new_token}, f, indent=2)
                    st.success("✅ Token salvo! Recarregue a página.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
            else:
                st.warning("Digite um token válido")
    
    else:
        # Home Assistant conectado!
        config = get_ha_config()
        st.success(f"✅ Conectado ao Home Assistant - {config.get('location_name', 'Casa')}")
        
        # Obter todos os dispositivos
        states = get_ha_states()
        
        # Separar por domínio
        lights = [s for s in states if s.get("entity_id", "").startswith("light.")]
        switches = [s for s in states if s.get("entity_id", "").startswith("switch.")]
        climate = [s for s in states if s.get("entity_id", "").startswith("climate.")]
        sensors = [s for s in states if s.get("entity_id", "").startswith("sensor.")]
        binary_sensors = [s for s in states if s.get("entity_id", "").startswith("binary_sensor.")]
        
        # Métricas
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            lights_on = len([l for l in lights if l.get("state") == "on"])
            st.metric("💡 Luzes", f"{lights_on}/{len(lights)}", f"{lights_on} ligadas")
        with col2:
            switches_on = len([s for s in switches if s.get("state") == "on"])
            st.metric("🔌 Tomadas", f"{switches_on}/{len(switches)}", f"{switches_on} ligadas")
        with col3:
            st.metric("❄️ Climatização", len(climate))
        with col4:
            st.metric("📊 Sensores", len(sensors) + len(binary_sensors))
        
        st.markdown("---")
        
        # === LUZES ===
        if lights:
            st.subheader("💡 Luzes")
            cols = st.columns(min(len(lights), 4))
            for i, light in enumerate(lights):
                with cols[i % 4]:
                    entity_id = light.get("entity_id", "")
                    name = light.get("attributes", {}).get("friendly_name", entity_id.split(".")[-1])
                    state = light.get("state", "off")
                    
                    is_on = state == "on"
                    emoji = "💡" if is_on else "⚫"
                    
                    st.markdown(f"**{emoji} {name}**")
                    if st.button(f"{'Desligar' if is_on else 'Ligar'}", key=f"btn_{entity_id}"):
                        if is_on:
                            ha_turn_off(entity_id)
                        else:
                            ha_turn_on(entity_id)
                        st.rerun()
        
        # === TOMADAS/SWITCHES ===
        if switches:
            st.markdown("---")
            st.subheader("🔌 Tomadas e Interruptores")
            cols = st.columns(min(len(switches), 4))
            for i, switch in enumerate(switches):
                with cols[i % 4]:
                    entity_id = switch.get("entity_id", "")
                    name = switch.get("attributes", {}).get("friendly_name", entity_id.split(".")[-1])
                    state = switch.get("state", "off")
                    
                    is_on = state == "on"
                    emoji = "🟢" if is_on else "⚫"
                    
                    st.markdown(f"**{emoji} {name}**")
                    if st.button(f"{'Desligar' if is_on else 'Ligar'}", key=f"btn_{entity_id}"):
                        if is_on:
                            ha_turn_off(entity_id)
                        else:
                            ha_turn_on(entity_id)
                        st.rerun()
        
        # === CLIMATIZAÇÃO ===
        if climate:
            st.markdown("---")
            st.subheader("❄️ Climatização")
            for clim in climate:
                entity_id = clim.get("entity_id", "")
                name = clim.get("attributes", {}).get("friendly_name", entity_id.split(".")[-1])
                state = clim.get("state", "off")
                attrs = clim.get("attributes", {})
                
                current_temp = attrs.get("current_temperature", "?")
                target_temp = attrs.get("temperature", "?")
                
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.markdown(f"**{name}** - {state}")
                    st.caption(f"Atual: {current_temp}°C → Alvo: {target_temp}°C")
                with col2:
                    if st.button("Ligar", key=f"on_{entity_id}"):
                        ha_turn_on(entity_id)
                        st.rerun()
                with col3:
                    if st.button("Desligar", key=f"off_{entity_id}"):
                        ha_turn_off(entity_id)
                        st.rerun()
        
        # === SENSORES (resumo) ===
        if sensors or binary_sensors:
            st.markdown("---")
            with st.expander(f"📊 Sensores ({len(sensors) + len(binary_sensors)})"):
                for sensor in (sensors + binary_sensors)[:20]:
                    entity_id = sensor.get("entity_id", "")
                    name = sensor.get("attributes", {}).get("friendly_name", entity_id.split(".")[-1])
                    state = sensor.get("state", "?")
                    unit = sensor.get("attributes", {}).get("unit_of_measurement", "")
                    st.text(f"{name}: {state} {unit}")
        
        # === AÇÕES RÁPIDAS ===
        st.markdown("---")
        st.subheader("⚡ Ações Rápidas")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("💡 Ligar Todas Luzes"):
                for light in lights:
                    ha_turn_on(light.get("entity_id"))
                st.rerun()
        with col2:
            if st.button("🌙 Desligar Todas Luzes"):
                for light in lights:
                    ha_turn_off(light.get("entity_id"))
                st.rerun()
        with col3:
            if st.button("🔌 Ligar Tudo"):
                for device in lights + switches:
                    ha_turn_on(device.get("entity_id"))
                st.rerun()
        with col4:
            if st.button("⭕ Desligar Tudo"):
                for device in lights + switches:
                    ha_turn_off(device.get("entity_id"))
                st.rerun()

elif page == "📚 Collections":
    st.title("📚 Detalhes das Collections")
    
    stats = get_rag_stats()
    if stats:
        collections = stats.get('collections', [])
        
        for coll in collections:
            with st.expander(f"📁 {coll}", expanded=(coll == "bitcoin_knowledge")):
                # Teste de busca na collection
                test_result, latency = test_rag_search("teste", coll)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("⚡ Latência", f"{latency:.0f}ms")
                with col2:
                    if test_result:
                        n_results = len(test_result.get('results', []))
                        st.metric("📊 Resultados de Teste", n_results)
                
                if coll == "bitcoin_knowledge":
                    st.success("🪙 Esta collection contém conhecimento especializado em Bitcoin!")
                    st.markdown("""
                    **Tópicos cobertos:**
                    - Fundamentos do Bitcoin
                    - Blockchain e tecnologia
                    - Mineração e Halving
                    - Carteiras e segurança
                    - Lightning Network
                    - Taproot e SegWit
                    - ETFs e mercado
                    """)

elif page == "🔍 Teste de Busca":
    st.title("🔍 Teste de Busca RAG")
    
    stats = get_rag_stats()
    collections = stats.get('collections', ['default']) if stats else ['default']
    
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("Digite sua pergunta:", placeholder="Ex: O que é Bitcoin?")
    with col2:
        collection = st.selectbox("Collection:", collections)
    
    n_results = st.slider("Número de resultados:", 1, 10, 3)
    
    if st.button("🔍 Buscar", type="primary"):
        if query:
            with st.spinner("Buscando..."):
                result, latency = test_rag_search(query, collection)
            
            if result:
                st.success(f"✅ Busca concluída em {latency:.0f}ms")
                
                results = result.get('results', [])
                if results:
                    for i, r in enumerate(results):
                        with st.expander(f"📄 Resultado {i+1}", expanded=(i==0)):
                            content = r.get('content', 'N/A')
                            st.markdown(content[:1000] + "..." if len(content) > 1000 else content)
                            
                            metadata = r.get('metadata', {})
                            if metadata:
                                st.caption(f"📌 Tópico: {metadata.get('topic', 'N/A')} | Fonte: {metadata.get('source', 'N/A')}")
                else:
                    st.warning("⚠️ Nenhum resultado encontrado")
            else:
                st.error("❌ Erro na busca")
        else:
            st.warning("Digite uma pergunta")

elif page == "🧠 Teste de Inferência":
    st.title("🧠 Teste de Inferência Ollama")
    
    models = get_ollama_models()
    model_names = [m.get('name', 'unknown') for m in models] if models else ['llama3.2']
    
    col1, col2 = st.columns([3, 1])
    with col1:
        prompt = st.text_area("Digite seu prompt:", placeholder="Ex: Explique o que é Bitcoin em 3 frases.", height=100)
    with col2:
        model = st.selectbox("Modelo:", model_names)
    
    if st.button("🚀 Gerar", type="primary"):
        if prompt:
            with st.spinner(f"Gerando com {model}..."):
                result, latency = test_ollama_inference(prompt, model)
            
            if result:
                st.success(f"✅ Gerado em {latency/1000:.1f}s")
                
                response = result.get('response', 'N/A')
                st.markdown("### 📝 Resposta:")
                st.markdown(response)
                
                # Métricas
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("⚡ Latência", f"{latency/1000:.1f}s")
                with col2:
                    tokens = result.get('eval_count', 0)
                    st.metric("🔢 Tokens", tokens)
                with col3:
                    if tokens and latency:
                        tps = tokens / (latency/1000)
                        st.metric("📈 Tokens/s", f"{tps:.1f}")
            else:
                st.error("❌ Erro na inferência")
        else:
            st.warning("Digite um prompt")

elif page == "📈 Benchmark":
    st.title("📈 Benchmark de Performance")
    
    st.markdown("Execute testes automatizados para medir a performance do sistema.")
    
    if st.button("🚀 Iniciar Benchmark Completo", type="primary"):
        progress = st.progress(0)
        status = st.empty()
        
        results = {
            "rag_searches": [],
            "ollama_inferences": []
        }
        
        # Benchmark RAG
        test_queries = [
            ("O que é Bitcoin?", "bitcoin_knowledge"),
            ("Como funciona a blockchain?", "bitcoin_knowledge"),
            ("O que é Lightning Network?", "bitcoin_knowledge"),
            ("Quem é Satoshi Nakamoto?", "bitcoin_knowledge"),
            ("O que é halving?", "bitcoin_knowledge"),
        ]
        
        status.info("🔍 Testando buscas RAG...")
        for i, (q, coll) in enumerate(test_queries):
            _, latency = test_rag_search(q, coll)
            results["rag_searches"].append({"query": q, "latency": latency})
            progress.progress((i + 1) / (len(test_queries) + 3) * 100 / 100)
        
        # Benchmark Ollama
        status.info("🧠 Testando inferência Ollama...")
        test_prompts = [
            "Responda em uma frase: O que é Bitcoin?",
            "Diga apenas sim ou não: Bitcoin é descentralizado?",
            "Complete: A blockchain do Bitcoin é..."
        ]
        
        for i, p in enumerate(test_prompts):
            _, latency = test_ollama_inference(p)
            results["ollama_inferences"].append({"prompt": p[:30], "latency": latency})
            progress.progress((len(test_queries) + i + 1) / (len(test_queries) + 3) * 100 / 100)
        
        progress.progress(100)
        status.success("✅ Benchmark concluído!")
        
        # Resultados
        st.markdown("---")
        st.subheader("📊 Resultados")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🔍 RAG Search")
            rag_latencies = [r['latency'] for r in results['rag_searches']]
            avg_rag = sum(rag_latencies) / len(rag_latencies) if rag_latencies else 0
            
            st.metric("Latência Média", f"{avg_rag:.0f}ms")
            st.metric("Latência Mínima", f"{min(rag_latencies):.0f}ms" if rag_latencies else "N/A")
            st.metric("Latência Máxima", f"{max(rag_latencies):.0f}ms" if rag_latencies else "N/A")
            
            # Classificação
            if avg_rag < 100:
                st.success("🏆 Excelente performance!")
            elif avg_rag < 300:
                st.info("✅ Boa performance")
            else:
                st.warning("⚠️ Performance pode ser melhorada")
        
        with col2:
            st.markdown("### 🧠 Ollama Inference")
            ollama_latencies = [r['latency'] for r in results['ollama_inferences']]
            avg_ollama = sum(ollama_latencies) / len(ollama_latencies) if ollama_latencies else 0
            
            st.metric("Latência Média", f"{avg_ollama/1000:.1f}s")
            st.metric("Latência Mínima", f"{min(ollama_latencies)/1000:.1f}s" if ollama_latencies else "N/A")
            st.metric("Latência Máxima", f"{max(ollama_latencies)/1000:.1f}s" if ollama_latencies else "N/A")
            
            # Classificação
            if avg_ollama < 2000:
                st.success("🏆 Excelente performance!")
            elif avg_ollama < 5000:
                st.info("✅ Boa performance")
            else:
                st.warning("⚠️ Performance pode ser melhorada")
        
        # Detalhes
        st.markdown("---")
        st.subheader("📋 Detalhes dos Testes")
        
        with st.expander("🔍 Detalhes RAG"):
            for r in results['rag_searches']:
                st.write(f"- **{r['query']}**: {r['latency']:.0f}ms")
        
        with st.expander("🧠 Detalhes Ollama"):
            for r in results['ollama_inferences']:
                st.write(f"- **{r['prompt']}...**: {r['latency']/1000:.1f}s")

# Footer
st.markdown("---")
st.caption("🤖 RAG AI Dashboard v1.0 | Monitoramento em tempo real do sistema de IA")
