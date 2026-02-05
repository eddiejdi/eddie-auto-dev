import os
import sys
import builtins

# Adiciona o diretório pai ao sys.path para permitir import de main.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from main import (
        clone_repository,
        build_docker_image,
        deploy_with_kubectl,
        check_app_accessibility,
        check_api_endpoint,
    )
except Exception:
    # Silencioso: se import falhar, testes irão mostrar erros explícitos
    clone_repository = build_docker_image = deploy_with_kubectl = None
    check_app_accessibility = check_api_endpoint = None

# Injeta as funções no builtins para que os testes que chamam nomes diretamente funcionem
builtins.clone_repository = clone_repository
builtins.build_docker_image = build_docker_image
builtins.deploy_with_kubectl = deploy_with_kubectl
builtins.check_app_accessibility = check_app_accessibility
builtins.check_api_endpoint = check_api_endpoint
