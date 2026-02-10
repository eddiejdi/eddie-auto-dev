# Dev Agent - Agente Programador Autonomo 🤖

Cria codigo, testa em Docker e corrige automaticamente ate funcionar.

## Funcionalidades

- 🧠 Integracao com LLM (Ollama)
- 🐳 Docker automatico
- 🔄 Auto-correcao de erros
- 🧪 Testes automatizados
- 🌐 Interface Streamlit

## Tecnologias Suportadas

Python, Selenium, Streamlit, SQL, FastAPI, Flask, Django, Scrapy, Pandas

## Instalacao

```bash
pip install -r requirements.txt
## Uso

### Interface Web
```bash
streamlit run streamlit_app.py
### Via Python
import asyncio
from dev_agent.agent import DevAgent, develop

async def main():
    result = await develop("Crie uma API REST...")
    print(result["code"])

asyncio.run(main())
## Configuracao

- OLLAMA_HOST: URL do Ollama (default: http://192.168.15.2:11434)
- OLLAMA_MODEL: Modelo (default: codellama:13b)
