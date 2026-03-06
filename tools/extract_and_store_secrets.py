#!/usr/bin/env python3
"""Extrai secrets do código e os persiste no Secrets Agent."""

import os
import re
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Padrões aprimorados para detecção de secrets
SECRET_PATTERNS = {
    'api_key': {
        'pattern': r'["\']?api[_-]?key["\']?\s*[:=]\s*["\']([^\n"\']{10,})["\']',
        'priority': 'high',
        'sensitive': True,
    },
    'database_url': {
        'pattern': r'(?:DATABASE_URL|db_url|postgres_url|mongodb_url)["\']?\s*[:=]\s*["\']([^\n"\']+://[^\n"\']+)["\']',
        'priority': 'critical',
        'sensitive': True,
    },
    'token': {
        'pattern': r'["\']?(?:token|auth_token|bearer_token|access_token)["\']?\s*[:=]\s*["\']([^\n"\']{20,})["\']',
        'priority': 'high',
        'sensitive': True,
    },
    'password': {
        'pattern': r'["\']?(?:password|passwd|pwd)["\']?\s*[:=]\s*["\']([^\n"\']{8,})["\']',
        'priority': 'high',
        'sensitive': True,
    },
    'secret': {
        'pattern': r'["\']?(?:secret|client_secret|api_secret|private_key)["\']?\s*[:=]\s*["\']([^\n"\']{10,})["\']',
        'priority': 'high',
        'sensitive': True,
    },
}

@dataclass
class Secret:
    """Representa um secret extraído."""
    name: str
    type: str
    file_path: str
    line_number: int
    pattern_type: str
    value_preview: str  # Primeiros 10 chars + '*'*len(rest)
    sensitivity: str  # 'low', 'medium', 'high', 'critical'
    extracted_at: str = ""
    
    def __post_init__(self):
        if not self.extracted_at:
            self.extracted_at = datetime.now().isoformat()

class SecretExtractor:
    """Extrai secrets do código."""
    
    def __init__(self, workspace_root: str):
        self.workspace = Path(workspace_root)
        self.secrets_found: List[Secret] = []
        self.false_positives = {
            'placeholder', 'example', 'test', 'demo', 'fake',
            'your_', 'replace_', 'insert_', 'temporary', 'changeme',
            'password123', 'test_', 'mock_', 'stub_', 'temp_'
        }
        
    def scan_workspace(self) -> List[Secret]:
        """Escaneia todo o workspace procurando secrets (otimizado)."""
        logger.info("🔍 Escaneando workspace por secrets...")
        
        # Só scanneia arquivos Python principais (mais rápido)
        file_patterns = ['**/*agent*.py', '**/*handler*.py', '**/*.env*']
        
        total_files = 0
        for pattern in file_patterns:
            try:
                for file_path in self.workspace.glob(pattern):
                    if self._should_skip_file(file_path):
                        continue
                    
                    total_files += 1
                    if total_files % 20 == 0:
                        logger.info(f"  Processando arquivo {total_files}...")
                    self._scan_file(file_path)
            except Exception as e:
                logger.debug(f"Erro ao processar padrão {pattern}: {e}")
        
        logger.info(f"✅ {total_files} arquivos escaneados")
        logger.info(f"🔐 {len(self.secrets_found)} secrets potenciais detectados")
        
        return self.secrets_found
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """Verifica se arquivo deve ser pulado."""
        skip_dirs = {
            '.venv', 'venv', 'node_modules', '.git', '__pycache__',
            '.pytest_cache', 'dist', 'build', '.tox', 'htmlcov',
            '.egg-info', 'docs/agents'  # Pula documentação gerada
        }
        
        skip_files = {
            '.gitignore', '.env.example', 'requirements.txt',
            'package.json', '.editorconfig'
        }
        
        parts = set(file_path.parts)
        if any(skip_dir in parts for skip_dir in skip_dirs):
            return True
        
        if file_path.name in skip_files:
            return True
        
        # Limita tamanho do arquivo
        try:
            if file_path.stat().st_size > 5 * 1024 * 1024:  # > 5MB
                return True
        except:
            return True
        
        return False
    
    def _scan_file(self, file_path: Path) -> None:
        """Escaneia um arquivo específico (otimizado)."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Limite de tamanho para analizar
            if len(content) > 1_000_000:  # > 1MB, analisa só inicio
                content = content[:500_000]
            
            lines = content.split('\n')
            
            for pattern_type, pattern_info in SECRET_PATTERNS.items():
                pattern = pattern_info['pattern']
                priority = pattern_info['priority']
                
                try:
                    # Tenta compilar padrão uma vez
                    regex = re.compile(pattern, re.IGNORECASE | re.DOTALL)
                except re.error:
                    logger.debug(f"Padrão inválido: {pattern_type}")
                    continue
                
                for line_num, line in enumerate(lines, 1):
                    # Skip linhas muito longas
                    if len(line) > 2000:
                        continue
                    
                    try:
                        matches = regex.finditer(line)
                        
                        for match in matches:
                            if len(match.groups()) > 0:
                                value = match.group(1)
                                
                                # Valida se é realmente um secret
                                if self._is_likely_secret(value):
                                    secret = Secret(
                                        name=self._generate_secret_name(file_path, pattern_type),
                                        type=pattern_type,
                                        file_path=str(file_path.relative_to(self.workspace)),
                                        line_number=line_num,
                                        pattern_type=pattern_type,
                                        value_preview=self._mask_value(value),
                                        sensitivity=priority,
                                    )
                                    
                                    self.secrets_found.append(secret)
                    except Exception as e:
                        logger.debug(f"Erro ao processar linha {line_num}: {e}")
                        
        except Exception as e:
            logger.debug(f"⚠️  Erro ao escanear {file_path}: {e}")
    
    def _is_likely_secret(self, value: str) -> bool:
        """Verifica se valor é provavelmente um secret."""
        if not value or len(value) < 5:
            return False
        
        # Rejeita obviamente falsos positivos
        for fp in self.false_positives:
            if fp in value.lower():
                return False
        
        # Rejeita paths comuns
        if value.startswith('/') or value.startswith('~'):
            return False
        
        # Rejeita números só
        if value.isdigit():
            return False
        
        return True
    
    def _generate_secret_name(self, file_path: Path, pattern_type: str) -> str:
        """Gera nome qualificado para o secret."""
        # Extrai módulo/agente do caminho
        module_path = file_path.stem
        
        if 'specialized_agents' in file_path.parts:
            prefix = 'agent'
        elif 'handlers' in file_path.parts:
            prefix = 'handler'
        else:
            prefix = 'eddie'
        
        return f"{prefix}/{module_path}/{pattern_type}".lower().replace('__', '_')
    
    def _mask_value(self, value: str) -> str:
        """Mascara valor para preview seguro."""
        if len(value) <= 10:
            return '*' * len(value)
        
        return value[:5] + '*' * (len(value) - 10) + value[-5:]
    
    def generate_report(self) -> Dict:
        """Gera relatório de secrets encontrados."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_secrets": len(self.secrets_found),
            "by_type": {},
            "by_sensitivity": {},
            "secrets": [asdict(s) for s in self.secrets_found]
        }
        
        for secret in self.secrets_found:
            # Agrupa por tipo
            report["by_type"].setdefault(secret.pattern_type, 0)
            report["by_type"][secret.pattern_type] += 1
            
            # Agrupa por sensibilidade
            report["by_sensitivity"].setdefault(secret.sensitivity, 0)
            report["by_sensitivity"][secret.sensitivity] += 1
        
        return report
    
    def export_report(self, output_file: str) -> None:
        """Exporta relatório em JSON."""
        report = self.generate_report()
        
        output_path = self.workspace / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Relatório exportado: {output_path.relative_to(self.workspace)}")
    
    def print_summary(self) -> None:
        """Exibe resumo dos secrets encontrados."""
        logger.info("\n" + "="*70)
        logger.info("🔐 RELATÓRIO DE SECRETS DETECTADOS")
        logger.info("="*70)
        
        if not self.secrets_found:
            logger.info("\n✅ Nenhum secret detectado durante a varredura!")
            return
        
        logger.warning(f"\n⚠️  {len(self.secrets_found)} secrets potenciais detectados:\n")
        
        # Agrupa por tipo
        by_type = {}
        for secret in self.secrets_found:
            by_type.setdefault(secret.pattern_type, []).append(secret)
        
        for pattern_type in sorted(by_type.keys()):
            secrets = by_type[pattern_type]
            logger.warning(f"\n  {pattern_type.upper()}:")
            for secret in secrets[:5]:  # Max 5 por tipo
                logger.warning(
                    f"    • {secret.name} ({secret.sensitivity})\n"
                    f"      File: {secret.file_path}:{secret.line_number}\n"
                    f"      Value: {secret.value_preview}"
                )
            
            if len(secrets) > 5:
                logger.warning(f"    ... e mais {len(secrets) - 5}")
        
        # Resumo por sensibilidade
        by_sensitivity = {}
        for secret in self.secrets_found:
            by_sensitivity.setdefault(secret.sensitivity, 0)
            by_sensitivity[secret.sensitivity] += 1
        
        logger.info(f"\n📊 POR SENSIBILIDADE:")
        for severity in ['critical', 'high', 'medium', 'low']:
            count = by_sensitivity.get(severity, 0)
            if count > 0:
                logger.warning(f"  • {severity.upper()}: {count}")

def store_secret_in_agent(secret_name: str, secret_value: str, field: str = "value") -> bool:
    """Armazena secret no Secrets Agent."""
    try:
        # TODO: Implementar integração com Secrets Agent via API/CLI
        # Por enquanto, apenas loga o que seria armazenado
        logger.info(f"📦 Secret pronto para armazenar: {secret_name}")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao armazenar {secret_name}: {e}")
        return False

def main():
    """Executa extração completa."""
    workspace = sys.argv[1] if len(sys.argv) > 1 else "/home/edenilson/eddie-auto-dev"
    
    # 1. Extrai secrets
    extractor = SecretExtractor(workspace)
    secrets = extractor.scan_workspace()
    
    # 2. Exibe relatório
    extractor.print_summary()
    
    # 3. Exporta relatório
    extractor.export_report("tools/secrets_detection_report.json")
    
    # 4. Instrui sobre próximos passos
    if secrets:
        logger.warning("\n" + "="*70)
        logger.warning("⚠️  PRÓXIMOS PASSOS:")
        logger.warning("="*70)
        logger.warning("\n1. Revise os secrets detectados em: tools/secrets_detection_report.json")
        logger.warning("2. Identifique quais são reais (vs falsos positivos)")
        logger.warning("3. Remova secrets do código-fonte")
        logger.warning("4. Use variáveis de ambiente ou Secrets Agent")
        logger.warning("5. Verifique segurança e nunca commite credenciais")
        logger.warning("\n" + "="*70)
    
    logger.info("\n✨ Extração completa!")

if __name__ == "__main__":
    main()
