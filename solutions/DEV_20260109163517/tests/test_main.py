import pytest
from unittest.mock import patch


# Mock da função run do subprocess
@patch("subprocess.run")
def test_clone_repository(mock_run):
    repo_url = "https://github.com/yourusername/your-repo.git"
    clone_repository(repo_url)
    mock_run.assert_called_once_with(["git", "clone", repo_url], check=True)


# Mock da função run do subprocess
@patch("subprocess.run")
def test_build_docker_image(mock_run):
    image_name = "your-image-name"
    build_docker_image(image_name)
    mock_run.assert_called_once_with(
        ["docker", "build", "-t", image_name, "."], check=True
    )


# Mock da função run do subprocess
@patch("subprocess.run")
def test_deploy_with_kubectl(mock_run):
    image_name = "your-image-name"
    deploy_with_kubectl(image_name)
    mock_run.assert_called_once_with(
        ["kubectl", "run", image_name, "--image", image_name], check=True
    )


# Mock da função run do subprocess
@patch("subprocess.run")
def test_check_app_accessibility(mock_run):
    url = "http://localhost:8080"
    check_app_accessibility(url)
    mock_run.assert_called_once_with(
        ["curl", "-s", url], capture_output=True, text=True
    )


# Mock da função run do subprocess
@patch("subprocess.run")
def test_check_api_endpoint(mock_run):
    url = "http://localhost:8080/api/v1/health"
    check_api_endpoint(url)
    mock_run.assert_called_once_with(
        ["curl", "-s", f"{url}/api/v1/health"], capture_output=True, text=True
    )


# Caso de sucesso com valores válidos
def test_clone_repository_success():
    repo_url = "https://github.com/yourusername/your-repo.git"
    clone_repository(repo_url)
    assert True


# Caso de erro (divisão por zero)
def test_build_docker_image_error():
    image_name = "your-image-name"
    with pytest.raises(Exception) as e:
        build_docker_image(image_name)
    assert str(e.value).startswith("Erro ao construir a imagem Docker")


# Edge case (valores limite)
def test_check_app_accessibility_edge_case():
    url = "http://localhost:8080"
    check_app_accessibility(url)
    assert True


# Edge case (string vazia)
def test_check_api_endpoint_edge_case():
    url = ""
    with pytest.raises(Exception) as e:
        check_api_endpoint(url)
    assert str(e.value).startswith("Erro ao verificar o endpoint 'health'")
