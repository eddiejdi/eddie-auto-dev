#!/usr/bin/env python3
"""
Unit tests for Variables Catalog Scanner
Tests variable detection, classification, and catalog generation
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.catalog_variables import VariablesCatalog


class TestVariablesCatalog:
    """Test suite for VariablesCatalog class."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Create subdirectories
            (tmppath / "config").mkdir()
            (tmppath / "systemd").mkdir()
            
            yield tmppath
    
    @pytest.fixture
    def catalog(self, temp_workspace):
        """Create catalog instance with temp workspace."""
        return VariablesCatalog(root_path=str(temp_workspace))
    
    # ========================================================================
    # TEST ENV FILE PARSING
    # ========================================================================
    
    def test_parse_simple_env_file(self, catalog, temp_workspace):
        """Test parsing a simple .env file."""
        env_file = temp_workspace / ".env"
        env_file.write_text("""
# Database config
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
DB_POOL_SIZE=10

# API config
API_PORT=8503
API_HOST=0.0.0.0
""")
        
        result = catalog.scan_env_files()
        
        assert "DATABASE_URL" in result
        assert "API_PORT" in result
        assert result["DATABASE_URL"]["type"] == "url"
        assert result["API_PORT"]["type"] == "integer"
    
    def test_env_file_with_comments(self, catalog, temp_workspace):
        """Test that comments are properly skipped."""
        env_file = temp_workspace / ".env"
        env_file.write_text("""
# This is a comment
MY_VAR=value  # inline comment (not parsed)
ANOTHER_VAR=123
""")
        
        result = catalog.scan_env_files()
        assert "MY_VAR" in result
        assert "ANOTHER_VAR" in result
        assert len(result) == 2
    
    def test_sensitive_variable_redaction(self, catalog, temp_workspace):
        """Test that sensitive variables are redacted."""
        env_file = temp_workspace / ".env"
        env_file.write_text("""
API_KEY=super_secret_key_12345
JWT_SECRET=my_jwt_secret
NORMAL_VAR=public_value
PASSWORD=secretpassword
""")
        
        result = catalog.scan_env_files()
        
        assert result["API_KEY"]["value"] == "***REDACTED***"
        assert result["JWT_SECRET"]["value"] == "***REDACTED***"
        assert result["NORMAL_VAR"]["value"] == "public_value"
        assert result["PASSWORD"]["value"] == "***REDACTED***"
    
    def test_env_file_locations(self, catalog, temp_workspace):
        """Test that file locations are tracked."""
        env_file = temp_workspace / ".env"
        env_file.write_text("""
VAR1=value1
VAR2=value2
""")
        
        result = catalog.scan_env_files()
        
        assert "locations" in result["VAR1"]
        assert len(result["VAR1"]["locations"]) >= 1
        assert result["VAR1"]["locations"][0]["line"] == 2
    
    # ========================================================================
    # TEST TYPE INFERENCE
    # ========================================================================
    
    def test_type_inference_url(self, catalog):
        """Test URL type detection."""
        assert catalog._infer_type("https://example.com") == "url"
        assert catalog._infer_type("http://localhost:8000") == "url"
    
    def test_type_inference_path(self, catalog):
        """Test path type detection."""
        assert catalog._infer_type("/var/log/app.log") == "path"
        assert catalog._infer_type("/usr/local/bin") == "path"
    
    def test_type_inference_integer(self, catalog):
        """Test integer type detection."""
        assert catalog._infer_type("8503") == "integer"
        assert catalog._infer_type("5432") == "integer"
    
    def test_type_inference_float(self, catalog):
        """Test float type detection."""
        assert catalog._infer_type("3.14") == "float"
        assert catalog._infer_type("0.5") == "float"
    
    def test_type_inference_boolean(self, catalog):
        """Test boolean type detection."""
        assert catalog._infer_type("true") == "boolean"
        assert catalog._infer_type("false") == "boolean"
        assert catalog._infer_type("True") == "boolean"
        assert catalog._infer_type("yes") == "boolean"
    
    def test_type_inference_json(self, catalog):
        """Test JSON type detection."""
        assert catalog._infer_type('{"key": "value"}') == "json"
        assert catalog._infer_type('[1, 2, 3]') == "json"
    
    # ========================================================================
    # TEST SENSITIVE DETECTION
    # ========================================================================
    
    def test_sensitive_keywords(self, catalog):
        """Test sensitive keyword detection."""
        sensitive_vars = [
            "API_SECRET",
            "DATABASE_PASSWORD",
            "JWT_TOKEN",
            "PRIVATE_KEY",
            "OAUTH_TOKEN",
        ]
        
        for var in sensitive_vars:
            assert catalog._is_sensitive(var), f"{var} should be marked sensitive"
    
    def test_non_sensitive_variables(self, catalog):
        """Test that non-sensitive variables are identified."""
        non_sensitive_vars = [
            "API_HOST",
            "API_PORT",
            "DATABASE_URL",  # URL without password is not sensitive
            "LOG_LEVEL",
        ]
        
        for var in non_sensitive_vars:
            assert not catalog._is_sensitive(var), f"{var} should not be marked sensitive"
    
    # ========================================================================
    # TEST DOCKER COMPOSE SCANNING
    # ========================================================================
    
    def test_parse_docker_compose(self, catalog, temp_workspace):
        """Test parsing docker-compose.yml."""
        compose_file = temp_workspace / "docker-compose.yml"
        compose_file.write_text("""
version: '3.8'
services:
  postgres:
    environment:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: secret123
      POSTGRES_DB: trading
  api:
    environment:
      - API_PORT=8503
      - DATABASE_URL=postgresql://localhost/trading
""")
        
        result = catalog.scan_docker_compose()
        
        assert "POSTGRES_USER" in result
        assert "POSTGRES_PASSWORD" in result
        assert "API_PORT" in result
        assert "DATABASE_URL" in result
    
    # ========================================================================
    # TEST CATEGORIZATION
    # ========================================================================
    
    def test_categorization_database(self, catalog):
        """Test database variable categorization."""
        test_vars = {
            "DATABASE_URL": {"name": "DATABASE_URL", "type": "string"},
            "DB_HOST": {"name": "DB_HOST", "type": "string"},
            "POSTGRES_PASSWORD": {"name": "POSTGRES_PASSWORD", "type": "string"},
        }
        
        catalog.categorize_variables(test_vars)
        
        assert "DATABASE_URL" in catalog.catalog["categories"]["database"]
        assert "DB_HOST" in catalog.catalog["categories"]["database"]
    
    def test_categorization_authentication(self, catalog):
        """Test authentication variable categorization."""
        test_vars = {
            "API_KEY": {"name": "API_KEY", "type": "string"},
            "JWT_SECRET": {"name": "JWT_SECRET", "type": "string"},
            "OAUTH_TOKEN": {"name": "OAUTH_TOKEN", "type": "string"},
        }
        
        catalog.categorize_variables(test_vars)
        
        assert "API_KEY" in catalog.catalog["categories"]["authentication"]
        assert "JWT_SECRET" in catalog.catalog["categories"]["authentication"]
    
    def test_categorization_trading(self, catalog):
        """Test trading variable categorization."""
        test_vars = {
            "EXCHANGE_API_KEY": {"name": "EXCHANGE_API_KEY", "type": "string"},
            "TRADING_DRY_RUN": {"name": "TRADING_DRY_RUN", "type": "boolean"},
            "MT5_ACCOUNT": {"name": "MT5_ACCOUNT", "type": "string"},
        }
        
        catalog.categorize_variables(test_vars)
        
        assert "EXCHANGE_API_KEY" in catalog.catalog["categories"]["trading"]
        assert "TRADING_DRY_RUN" in catalog.catalog["categories"]["trading"]
    
    # ========================================================================
    # TEST CATALOG GENERATION
    # ========================================================================
    
    def test_catalog_generation(self, catalog, temp_workspace):
        """Test complete catalog generation."""
        # Create test files
        (temp_workspace / ".env").write_text("API_KEY=secret\nAPI_PORT=8503\n")
        (temp_workspace / ".env.example").write_text("API_KEY=example_key\nAPI_PORT=8000\n")
        
        result = catalog.generate_catalog()
        
        assert result["catalogVersion"] == "1.0.0"
        assert "generatedAt" in result
        assert "categories" in result
        assert len(result["categories"]) > 0
    
    def test_catalog_metadata(self, catalog, temp_workspace):
        """Test catalog metadata generation."""
        (temp_workspace / ".env").write_text("VAR1=value1\nVAR2=value2\n")
        
        catalog.generate_catalog()
        
        assert catalog.catalog["metadata"]["totalVariables"] == 2
        assert len(catalog.catalog["metadata"]["sourceFiles"]) > 0
    
    # ========================================================================
    # TEST CATALOG EXPORT
    # ========================================================================
    
    def test_save_catalog_json(self, catalog, temp_workspace):
        """Test saving catalog to JSON."""
        output_file = temp_workspace / "catalog.json"
        
        # Create minimal catalog
        catalog.catalog = {
            "catalogVersion": "1.0.0",
            "generatedAt": "2026-06-21T00:00:00",
            "environment": "test",
            "categories": {
                "test": {
                    "TEST_VAR": {
                        "name": "TEST_VAR",
                        "type": "string",
                        "source": ".env"
                    }
                }
            }
        }
        
        catalog.save_catalog(str(output_file))
        
        assert output_file.exists()
        
        # Verify JSON is valid
        with open(output_file) as f:
            data = json.load(f)
        assert data["catalogVersion"] == "1.0.0"
    
    # ========================================================================
    # TEST ERROR HANDLING
    # ========================================================================
    
    def test_missing_env_file(self, catalog):
        """Test graceful handling of missing files."""
        result = catalog.scan_env_files()
        assert isinstance(result, dict)
    
    def test_invalid_yaml_handling(self, catalog, temp_workspace):
        """Test graceful handling of invalid YAML."""
        yaml_file = temp_workspace / "config.yml"
        yaml_file.write_text("invalid: yaml: content: [")
        
        result = catalog.scan_yaml_configs()
        # Should not crash, just skip the file
        assert isinstance(result, dict)
    
    def test_unreadable_file(self, catalog, temp_workspace):
        """Test handling of permission errors."""
        env_file = temp_workspace / ".env"
        env_file.write_text("VAR=value")
        
        # Mock file reading to raise permission error
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            result = catalog.scan_env_files()
            # Should handle error gracefully
            assert isinstance(result, dict)


class TestVariableTypes:
    """Test variable type classification."""
    
    def test_all_type_patterns_exist(self):
        """Ensure all required type patterns are defined."""
        from _variables_catalog_config import TYPE_PATTERNS
        
        required_types = ['url', 'path', 'integer', 'float', 'boolean', 'json']
        for type_name in required_types:
            assert type_name in TYPE_PATTERNS
    
    def test_sensitive_keywords_defined(self):
        """Ensure sensitive keywords are comprehensive."""
        from _variables_catalog_config import SENSITIVE_KEYWORDS
        
        assert len(SENSITIVE_KEYWORDS) > 10
        assert 'secret' in [k.lower() for k in SENSITIVE_KEYWORDS]
        assert 'password' in [k.lower() for k in SENSITIVE_KEYWORDS]
        assert 'token' in [k.lower() for k in SENSITIVE_KEYWORDS]


class TestServiceDefinitions:
    """Test service definitions."""
    
    def test_all_services_have_required_fields(self):
        """Ensure service definitions are complete."""
        from _variables_catalog_config import SERVICES
        
        required_fields = ['name', 'description', 'vars_prefix', 'dependencies', 'critical_vars']
        
        for service_name, service_config in SERVICES.items():
            for field in required_fields:
                assert field in service_config, f"Service {service_name} missing {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=tools.catalog_variables", "--cov-report=html"])
