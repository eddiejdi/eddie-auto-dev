# Eddie Mobile (scaffold)

Projeto minimal em Python usando Kivy para Android e iOS.

## Rodar no desktop (dev rápido)

1. Crie e ative um virtualenv

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
## Empacotar para Android (Buildozer)

1. Instale buildozer no host (Linux): `pip install buildozer`
2. Instale dependências do sistema (ex.: `sudo apt install -y build-essential git python3-pip openjdk-11-jdk zip unzip`)
3. Inicialize/edite spec: `buildozer init` (ou use o `buildozer.spec` aqui)
4. Build e deploy:

buildozer -v android debug
# para instalar no dispositivo:
buildozer android debug deploy run
Observação: empacotar para Android requer Linux (ou VM).

## Empacotar para iOS (kivy-ios)

1. Consulte https://kivy.org/doc/stable/guide/packaging-ios.html — é necessário macOS e Xcode.
2. `kivy-ios` cria um projeto Xcode; siga a documentação oficial.

## Notas
- Este scaffolding usa Kivy. Outra opção é BeeWare/Toga + Briefcase.
- Ajuste `buildozer.spec` conforme necessidades (permissões, assets, ícones).
