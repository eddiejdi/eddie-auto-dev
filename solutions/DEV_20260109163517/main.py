#!/usr/bin/env python
"""
Teste de Deploy
Auto-desenvolvido em: 2026-01-09T16:39:11.379052
ID: DEV_20260109163517

Realizar um teste completo do deploy de uma aplicação para garantir que todos os componentes estejam funcionando corretamente e que não haja erros ou falhas na implantação.
"""

from subprocess import run


# Função para clonar o repositório da aplicação do GitHub ou GitLab
def clone_repository(repo_url):
    try:
        run(["git", "clone", repo_url], check=True)
        print("Repositório clonado com sucesso!")
    except Exception as e:
        print(f"Erro ao clonar o repositório: {e}")


# Função para construir a imagem Docker da aplicação
def build_docker_image(image_name):
    try:
        run(["docker", "build", "-t", image_name, "."], check=True)
        print(f"Imagem Docker '{image_name}' construída com sucesso!")
    except Exception as e:
        print(f"Erro ao construir a imagem Docker: {e}")


# Função para executar o deploy usando kubectl
def deploy_with_kubectl(image_name):
    try:
        run(["kubectl", "run", image_name, "--image", image_name], check=True)
        print("Deploy da aplicação concluído com sucesso!")
    except Exception as e:
        print(f"Erro ao executar o deploy: {e}")


# Função para verificar se a aplicação está acessível via URL
def check_app_accessibility(url):
    try:
        response = run(["curl", "-s", url], capture_output=True, text=True)
        if "200 OK" in response.stdout:
            print("Aplicação está acessível!")
        else:
            print("Falha ao acessar a aplicação.")
    except Exception as e:
        print(f"Erro ao verificar a URL: {e}")


# Função para realizar uma chamada à API principal para garantir que todos os endpoints estejam funcionando corretamente
def check_api_endpoint(url):
    try:
        response = run(
            ["curl", "-s", f"{url}/api/v1/health"], capture_output=True, text=True
        )
        if "200 OK" in response.stdout:
            print("Endpoint 'health' está funcionando!")
        else:
            print("Falha no endpoint 'health'.")
    except Exception as e:
        print(f"Erro ao verificar o endpoint 'health': {e}")


# Função principal para executar todos os testes de deploy
def main():
    repo_url = "https://github.com/yourusername/your-repo.git"
    image_name = "your-image-name"

    # Clonar o repositório
    clone_repository(repo_url)

    # Construir a imagem Docker
    build_docker_image(image_name)

    # Executar o deploy usando kubectl
    deploy_with_kubectl(image_name)

    # Verificar se a aplicação está acessível via URL
    check_app_accessibility("http://localhost:8080")

    # Realizar uma chamada à API principal para garantir que todos os endpoints estejam funcionando corretamente
    check_api_endpoint("http://localhost:8080/api/v1/health")


if __name__ == "__main__":
    main()
