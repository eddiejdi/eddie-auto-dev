import pytest
from your_module import User, LoginManager, CLI

def test_register():
    login_manager = LoginManager()
    user = User("testuser", "testpassword")
    login_manager.register("testuser", "testpassword")
    assert login_manager.users["testuser"] == user

def test_login_success():
    login_manager = LoginManager()
    user = User("testuser", "testpassword")
    login_manager.register("testuser", "testpassword")
    cli = CLI(login_manager)
    cli.username = "testuser"
    cli.password = "testpassword"
    assert cli.login() == user

def test_login_failure():
    login_manager = LoginManager()
    user = User("testuser", "testpassword")
    login_manager.register("testuser", "testpassword")
    cli = CLI(login_manager)
    with pytest.raises(ValueError):
        cli.login()

def test_cli_start():
    login_manager = LoginManager()
    cli = CLI(login_manager)
    assert cli.start() == None