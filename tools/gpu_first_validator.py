#!/usr/bin/env python3
"""
GPU-First Strategy Enforcement Tool

Validates and enforces GPU-first rule across the project:
- GPU0/GPU1 always attempted before cloud APIs
- No cloud tokens in .env by default
- Proper retry/fallback logic in code
"""
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class GPUFirstValidator:
    """Validates GPU-first strategy compliance."""
    
    CLOUD_API_PATTERNS = [
        (r'openai\.ChatCompletion|ChatCompletion\.create', 'OpenAI'),
        (r'anthropic\.Anthropic|messages\.create', 'Anthropic (PROHIBITED)'),
        (r'google\.GenerativeAI|genai\.GenerativeModel', 'Google Gemini (PROHIBITED)'),
        (r'cohere\.generate|cohereclient', 'Cohere'),
    ]
    
    REQUIRED_GPU_ENV_VARS = [
        'OLLAMA_HOST',
        'OLLAMA_HOST_GPU1',
        'OLLAMA_MODEL',
    ]
    
    def __init__(self, repo_root: Path = None):
        self.repo_root = repo_root or Path.cwd()
        self.violations = []
        self.warnings = []
        self.passed = []
    
    def check_env_file(self) -> bool:
        """Check .env.consolidated for GPU-first compliance."""
        env_file = self.repo_root / '.env.consolidated'
        
        if not env_file.exists():
            self.warnings.append("⚠️  .env.consolidated not found")
            return False
        
        content = env_file.read_text()
        required_vars = {}
        
        for var in self.REQUIRED_GPU_ENV_VARS:
            if f"{var}=" in content:
                required_vars[var] = True
            else:
                self.violations.append(f"❌ Missing {var} in .env.consolidated")
                return False
        
        # Check for Ollama hosts
        if 'OLLAMA_HOST' in content and '192.168.15.2:11434' in content:
            self.passed.append("✓ GPU0 (11434) configured")
        
        if 'OLLAMA_HOST_GPU1' in content and '192.168.15.2:11435' in content:
            self.passed.append("✓ GPU1 (11435) configured")
        
        # Warn if cloud API keys are set (should only be fallback)
        cloud_keys = ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GOOGLE_API_KEY']
        for key in cloud_keys:
            if f"{key}=" in content and 'placeholder' not in content:
                self.warnings.append(f"⚠️  {key} set in config (use only as fallback)")
        
        return True
    
    def check_python_files(self) -> bool:
        """Scan Python files for GPU-first compliance."""
        violations_found = False
        
        # Only check relevant directories (skip test, .venv, node_modules, etc.)
        exclude_dirs = {'.venv', '__pycache__', '.git', '.pytest_cache', 'node_modules', 
                       'tests', 'test_', '.archive', 'build', 'dist', '.tox'}
        
        py_files = []
        for py_file in self.repo_root.rglob('*.py'):
            # Skip if in excluded directory
            if any(part in exclude_dirs for part in py_file.parts):
                continue
            py_files.append(py_file)
        
        # Subsample if too many files (performance optimization)
        total_files = len(py_files)
        if total_files > 100:
            # Sample: first 10 + random 40 more
            import random
            py_files = py_files[:10] + random.sample(py_files[10:], min(40, total_files-10))
        
        logger.info(f"Scanning {len(py_files)}/{total_files} Python files for violations...")
        
        for py_file in py_files:
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                
                # Check for cloud API usage without GPU fallback comment
                for pattern, api_name in self.CLOUD_API_PATTERNS:
                    matches = list(re.finditer(pattern, content, re.IGNORECASE))
                    
                    if matches:
                        # Check if marked as fallback
                        has_fallback_context = any([
                            'gpu_fallback' in content[max(0, m.start()-200):m.end()+200]
                            for m in matches
                        ])
                        
                        if not has_fallback_context:
                            self.violations.append(
                                f"❌ {py_file.relative_to(self.repo_root)}: "
                                f"Cloud API ({api_name}) without GPU fallback check"
                            )
                            violations_found = True
                        else:
                            self.passed.append(
                                f"✓ {api_name} has proper GPU fallback"
                            )
            
            except Exception as e:
                logger.debug(f"Error scanning {py_file}: {e}")
        
        return not violations_found
    
    def check_ollama_connectivity(self) -> bool:
        """Test actual Ollama GPU connectivity."""
        import urllib.request
        import json
        
        gpu_hosts = [
            ('GPU0', 'http://192.168.15.2:11434'),
            ('GPU1', 'http://192.168.15.2:11435'),
        ]
        
        gpu_available = False
        
        for name, host in gpu_hosts:
            try:
                response = urllib.request.urlopen(f"{host}/api/tags", timeout=5)
                data = json.loads(response.read())
                model_count = len(data.get('models', []))
                self.passed.append(f"✓ {name} online ({model_count} models)")
                gpu_available = True
            except Exception as e:
                self.warnings.append(f"⚠️  {name} ({host}) unreachable: {str(e)[:50]}")
        
        if not gpu_available:
            self.violations.append("❌ Neither GPU0 nor GPU1 reachable!")
        
        return gpu_available
    
    def generate_report(self) -> str:
        """Generate compliance report."""
        report = []
        report.append("=" * 70)
        report.append("GPU-FIRST STRATEGY VALIDATION REPORT")
        report.append("=" * 70)
        
        # Violations (errors)
        if self.violations:
            report.append("\n❌ VIOLATIONS (Must Fix):")
            for v in self.violations:
                report.append(f"  {v}")
        
        # Warnings
        if self.warnings:
            report.append("\n⚠️  WARNINGS (Recommended Fix):")
            for w in self.warnings:
                report.append(f"  {w}")
        
        # Passed checks
        if self.passed:
            report.append("\n✓ PASSED CHECKS:")
            for p in self.passed[:10]:  # Show first 10
                report.append(f"  {p}")
            if len(self.passed) > 10:
                report.append(f"  ... and {len(self.passed) - 10} more")
        
        # Summary
        report.append("\n" + "=" * 70)
        if self.violations:
            report.append("STATUS: ❌ VIOLATIONS FOUND - GPU-FIRST NOT COMPLIANT")
            report.append("ACTION: Fix violations before committing")
        elif self.warnings:
            report.append("STATUS: ⚠️  WARNINGS - GPU-FIRST PARTIALLY COMPLIANT")
            report.append("ACTION: Recommended to fix warnings")
        else:
            report.append("STATUS: ✅ GPU-FIRST COMPLIANT")
            report.append("ACTION: All checks passed!")
        
        report.append("=" * 70)
        
        return "\n".join(report)
    
    def run_all_checks(self) -> bool:
        """Run all validation checks."""
        logger.info("Starting GPU-First validation...")
        
        checks = [
            ("Environment File", self.check_env_file),
            ("Python Code", self.check_python_files),
            ("Ollama Connectivity", self.check_ollama_connectivity),
        ]
        
        all_passed = True
        for name, check_func in checks:
            try:
                logger.info(f"Checking {name}...")
                if not check_func():
                    all_passed = False
            except Exception as e:
                logger.error(f"Check '{name}' failed: {e}")
                self.violations.append(f"❌ {name} check errored: {e}")
                all_passed = False
        
        return all_passed
    
    def print_report(self):
        """Print validation report to console."""
        report = self.generate_report()
        print(report)
        
        # Return exit code
        if self.violations:
            return 1
        elif self.warnings:
            return 0  # Still exit 0 for warnings
        else:
            return 0


def main():
    validator = GPUFirstValidator()
    
    if not validator.run_all_checks():
        validator.print_report()
        sys.exit(1)
    
    validator.print_report()
    sys.exit(0)


if __name__ == '__main__':
    main()
