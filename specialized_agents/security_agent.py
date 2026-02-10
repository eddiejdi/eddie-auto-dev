"""
Security Agent para Eddie Auto-Dev
Responsável por análise de vulnerabilidades, compliance e segurança

Versão: 1.0.0
Criado: 2025-01-16
Autor: Diretor Eddie Auto-Dev
"""

import json
import hashlib
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

# Memória persistente (opcional)
try:
    from .agent_memory import get_agent_memory
    _MEMORY_AVAILABLE = True
except Exception:
    _MEMORY_AVAILABLE = False


class SeverityLevel(Enum):
    """Níveis de severidade de vulnerabilidades"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityType(Enum):
    """Tipos de vulnerabilidades detectáveis"""
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    CSRF = "csrf"
    HARDCODED_SECRET = "hardcoded_secret"
    INSECURE_DEPENDENCY = "insecure_dependency"
    WEAK_CRYPTO = "weak_crypto"
    PATH_TRAVERSAL = "path_traversal"
    COMMAND_INJECTION = "command_injection"
    INSECURE_DESERIALIZATION = "insecure_deserialization"
    SENSITIVE_DATA_EXPOSURE = "sensitive_data_exposure"
    BROKEN_AUTH = "broken_auth"
    MISCONFIGURATION = "misconfiguration"


@dataclass
class Vulnerability:
    """Representa uma vulnerabilidade encontrada"""
    id: str
    type: VulnerabilityType
    severity: SeverityLevel
    file_path: str
    line_number: int
    code_snippet: str
    description: str
    recommendation: str
    cwe_id: Optional[str] = None
    cvss_score: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "severity": self.severity.value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "code_snippet": self.code_snippet,
            "description": self.description,
            "recommendation": self.recommendation,
            "cwe_id": self.cwe_id,
            "cvss_score": self.cvss_score
        }


@dataclass
class SecurityReport:
    """Relatório de segurança"""
    scan_id: str
    timestamp: str
    target: str
    vulnerabilities: List[Vulnerability] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    compliance_status: Dict[str, bool] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "scan_id": self.scan_id,
            "timestamp": self.timestamp,
            "target": self.target,
            "vulnerabilities": [v.to_dict() for v in self.vulnerabilities],
            "summary": self.summary,
            "compliance_status": self.compliance_status
        }


class SecurityAgent:
    """
    Agent especializado em segurança para Eddie Auto-Dev.
    
    Responsabilidades:
    - Análise de vulnerabilidades (SAST)
    - Detecção de secrets hardcoded
    - Verificação de dependências vulneráveis
    - Compliance (OWASP, CWE, GDPR)
    - Recomendações de correção
    """
    
    VERSION = "1.0.0"
    
    # Regras herdadas conforme Regra 7
    AGENT_RULES = {
        "pipeline": {
            "description": "Seguir pipeline completo: Análise → Design → Código → Testes → Deploy",
            "mandatory": True,
            "phases": ["análise", "design", "código", "testes", "deploy"],
            "blocking": True
        },
        "token_economy": {
            "description": "Maximizar uso de recursos locais, minimizar GitHub Copilot",
            "mandatory": True,
            "prefer_local": True,
            "ollama_url": "http://192.168.15.2:11434",
            "copilot_only_for": ["problemas_nunca_vistos", "novos_assuntos", "acompanhamento", "feedback"]
        },
        "validation": {
            "description": "Sempre validar antes de entregar",
            "mandatory": True,
            "require_evidence": True,
            "test_at_each_step": True
        },
        "commit": {
            "description": "Commit obrigatório após testes com sucesso",
            "mandatory": True,
            "format": "feat|fix|security|refactor: descricao curta"
        },
        "communication": {
            "description": "Comunicar todas as ações via Communication Bus",
            "mandatory": True,
            "bus_integration": True
        },
        "security_specific": {
            "description": "Regras específicas de segurança",
            "mandatory": True,
            "scan_before_deploy": True,
            "block_critical_vulns": True,
            "require_remediation_plan": True,
            "compliance_frameworks": ["OWASP", "CWE", "GDPR"]
        }
    }
    
    # Padrões para detecção de secrets
    SECRET_PATTERNS = {
        "aws_access_key": r"AKIA[0-9A-Z]{16}",
        "aws_secret_key": r"[0-9a-zA-Z/+]{40}",
        "github_token": r"gh[pousr]_[A-Za-z0-9_]{36,}",
        "generic_api_key": r"(?i)(api[_-]?key|apikey)['\"]?\s*[:=]\s*['\"][a-zA-Z0-9]{16,}['\"]",
        "generic_secret": r"(?i)(secret|password|passwd|pwd)['\"]?\s*[:=]\s*['\"][^'\"]{8,}['\"]",
        "private_key": r"-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----",
        "jwt_token": r"eyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]*",
        "slack_token": r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*",
        "telegram_token": r"[0-9]{9,10}:[a-zA-Z0-9_-]{35}",
        "database_url": r"(?i)(mysql|postgres|mongodb|redis):\/\/[^\s]+",
    }
    
    # Padrões para SQL Injection
    SQL_INJECTION_PATTERNS = [
        r"execute\s*\(\s*['\"].*%s",
        r"cursor\.execute\s*\(\s*f['\"]",
        r"\.format\s*\(.*\).*(?:SELECT|INSERT|UPDATE|DELETE)",
        r"\+\s*['\"].*(?:SELECT|INSERT|UPDATE|DELETE)",
    ]
    
    # Padrões para XSS
    XSS_PATTERNS = [
        r"innerHTML\s*=",
        r"document\.write\s*\(",
        r"v-html\s*=",
        r"dangerouslySetInnerHTML",
        r"\|\s*safe\b",  # Django template
    ]
    
    # Padrões para Command Injection
    COMMAND_INJECTION_PATTERNS = [
        r"os\.system\s*\(",
        r"subprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True",
        r"eval\s*\(",
        r"exec\s*\(",
    ]
    
    def __init__(self, workspace_path: str = "."):
        self.workspace_path = Path(workspace_path)
        self.scan_count = 0
        self.vulnerabilities_found = []
        self.capabilities = {
            "name": "SecurityAgent",
            "version": self.VERSION,
            "specialization": "Application Security",
            "features": [
                "SAST (Static Application Security Testing)",
                "Secret Detection",
                "Dependency Scanning",
                "Compliance Checking (OWASP, CWE)",
                "Security Report Generation",
                "Remediation Recommendations"
            ],
            "rules_inherited": list(self.AGENT_RULES.keys()),
            "supported_languages": ["python", "javascript", "typescript", "go", "java"]
        }

        self.memory = None
        if _MEMORY_AVAILABLE:
            try:
                self.memory = get_agent_memory("security_agent")
            except Exception as e:
                print(f"[Warning] Memória indisponível para SecurityAgent: {e}")
    
    def get_rules(self) -> Dict[str, Any]:
        """Retorna as regras do agent conforme Regra 7"""
        return self.AGENT_RULES
    
    def validate_scan(self, report: SecurityReport) -> Dict[str, Any]:
        """
        Valida o scan conforme Regra 0.2
        Retorna evidências do scan realizado
        """
        validation = {
            "valid": True,
            "timestamp": datetime.now().isoformat(),
            "evidence": {
                "scan_id": report.scan_id,
                "files_scanned": report.summary.get("files_scanned", 0),
                "vulnerabilities_found": len(report.vulnerabilities),
                "by_severity": {
                    "critical": sum(1 for v in report.vulnerabilities if v.severity == SeverityLevel.CRITICAL),
                    "high": sum(1 for v in report.vulnerabilities if v.severity == SeverityLevel.HIGH),
                    "medium": sum(1 for v in report.vulnerabilities if v.severity == SeverityLevel.MEDIUM),
                    "low": sum(1 for v in report.vulnerabilities if v.severity == SeverityLevel.LOW),
                }
            },
            "compliance": report.compliance_status
        }
        
        # Bloquear se encontrar vulnerabilidades críticas (regra específica)
        if validation["evidence"]["by_severity"]["critical"] > 0:
            validation["valid"] = False
            validation["blocking_reason"] = "Critical vulnerabilities found - deployment blocked"
        
        return validation
    
    def generate_scan_id(self, target: str) -> str:
        """Gera ID único para o scan"""
        timestamp = datetime.now().isoformat()
        content = f"{target}-{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]
    
    def scan_secrets(self, file_path: Path, content: str) -> List[Vulnerability]:
        """Escaneia arquivo em busca de secrets hardcoded"""
        vulnerabilities = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for secret_type, pattern in self.SECRET_PATTERNS.items():
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    # Ignorar se estiver em comentário
                    if line.strip().startswith('#') or line.strip().startswith('//'):
                        continue
                    
                    vuln_id = f"SECRET-{self.scan_count:04d}"
                    self.scan_count += 1
                    
                    vulnerabilities.append(Vulnerability(
                        id=vuln_id,
                        type=VulnerabilityType.HARDCODED_SECRET,
                        severity=SeverityLevel.CRITICAL,
                        file_path=str(file_path),
                        line_number=line_num,
                        code_snippet=self._mask_secret(line.strip()),
                        description=f"Possível {secret_type.replace('_', ' ')} hardcoded detectado",
                        recommendation=f"Remova o secret do código e use variáveis de ambiente ou vault de secrets",
                        cwe_id="CWE-798",
                        cvss_score=9.0
                    ))
        
        return vulnerabilities
    
    def scan_sql_injection(self, file_path: Path, content: str) -> List[Vulnerability]:
        """Escaneia em busca de SQL Injection"""
        vulnerabilities = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for pattern in self.SQL_INJECTION_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    vuln_id = f"SQLI-{self.scan_count:04d}"
                    self.scan_count += 1
                    
                    vulnerabilities.append(Vulnerability(
                        id=vuln_id,
                        type=VulnerabilityType.SQL_INJECTION,
                        severity=SeverityLevel.CRITICAL,
                        file_path=str(file_path),
                        line_number=line_num,
                        code_snippet=line.strip()[:100],
                        description="Possível vulnerabilidade de SQL Injection - concatenação de strings em query SQL",
                        recommendation="Use prepared statements/parameterized queries em vez de concatenação de strings",
                        cwe_id="CWE-89",
                        cvss_score=9.8
                    ))
        
        return vulnerabilities
    
    def scan_xss(self, file_path: Path, content: str) -> List[Vulnerability]:
        """Escaneia em busca de XSS"""
        vulnerabilities = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for pattern in self.XSS_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    vuln_id = f"XSS-{self.scan_count:04d}"
                    self.scan_count += 1
                    
                    vulnerabilities.append(Vulnerability(
                        id=vuln_id,
                        type=VulnerabilityType.XSS,
                        severity=SeverityLevel.HIGH,
                        file_path=str(file_path),
                        line_number=line_num,
                        code_snippet=line.strip()[:100],
                        description="Possível vulnerabilidade de Cross-Site Scripting (XSS)",
                        recommendation="Sanitize user input e use funções de escape adequadas",
                        cwe_id="CWE-79",
                        cvss_score=7.5
                    ))
        
        return vulnerabilities
    
    def scan_command_injection(self, file_path: Path, content: str) -> List[Vulnerability]:
        """Escaneia em busca de Command Injection"""
        vulnerabilities = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for pattern in self.COMMAND_INJECTION_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    vuln_id = f"CMDI-{self.scan_count:04d}"
                    self.scan_count += 1
                    
                    vulnerabilities.append(Vulnerability(
                        id=vuln_id,
                        type=VulnerabilityType.COMMAND_INJECTION,
                        severity=SeverityLevel.CRITICAL,
                        file_path=str(file_path),
                        line_number=line_num,
                        code_snippet=line.strip()[:100],
                        description="Possível vulnerabilidade de Command Injection",
                        recommendation="Evite shell=True e use listas de argumentos com subprocess. Nunca use eval/exec com input do usuário",
                        cwe_id="CWE-78",
                        cvss_score=9.8
                    ))
        
        return vulnerabilities
    
    def scan_file(self, file_path: Path) -> List[Vulnerability]:
        """Escaneia um arquivo individual"""
        vulnerabilities = []
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            return vulnerabilities
        
        # Executar todos os scans
        vulnerabilities.extend(self.scan_secrets(file_path, content))
        vulnerabilities.extend(self.scan_sql_injection(file_path, content))
        vulnerabilities.extend(self.scan_xss(file_path, content))
        vulnerabilities.extend(self.scan_command_injection(file_path, content))
        
        return vulnerabilities
    
    def scan_directory(self, target_path: str = None, 
                       extensions: List[str] = None) -> SecurityReport:
        """
        Escaneia diretório inteiro em busca de vulnerabilidades
        
        Args:
            target_path: Caminho do diretório (default: workspace)
            extensions: Extensões de arquivo para escanear
        
        Returns:
            SecurityReport com todas as vulnerabilidades encontradas
        """
        if target_path is None:
            target_path = self.workspace_path
        else:
            target_path = Path(target_path)
        
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.java', '.php', '.rb']
        
        scan_id = self.generate_scan_id(str(target_path))
        vulnerabilities = []
        files_scanned = 0
        
        # Diretórios a ignorar
        ignore_dirs = {'.git', 'node_modules', '__pycache__', 'venv', '.venv', 'dist', 'build'}
        
        for file_path in target_path.rglob('*'):
            if file_path.is_file():
                # Verificar se está em diretório ignorado
                if any(ignored in file_path.parts for ignored in ignore_dirs):
                    continue
                
                if file_path.suffix in extensions:
                    files_scanned += 1
                    file_vulns = self.scan_file(file_path)
                    vulnerabilities.extend(file_vulns)
        
        # Calcular sumário
        summary = {
            "files_scanned": files_scanned,
            "total_vulnerabilities": len(vulnerabilities),
            "critical": sum(1 for v in vulnerabilities if v.severity == SeverityLevel.CRITICAL),
            "high": sum(1 for v in vulnerabilities if v.severity == SeverityLevel.HIGH),
            "medium": sum(1 for v in vulnerabilities if v.severity == SeverityLevel.MEDIUM),
            "low": sum(1 for v in vulnerabilities if v.severity == SeverityLevel.LOW),
        }
        
        # Verificar compliance
        compliance_status = self._check_compliance(vulnerabilities)
        
        report = SecurityReport(
            scan_id=scan_id,
            timestamp=datetime.now().isoformat(),
            target=str(target_path),
            vulnerabilities=vulnerabilities,
            summary=summary,
            compliance_status=compliance_status
        )
        
        return report
    
    def scan_dependencies(self, requirements_file: str = "requirements.txt") -> List[Vulnerability]:
        """
        Escaneia dependências em busca de vulnerabilidades conhecidas
        Usa pip-audit se disponível
        """
        vulnerabilities = []
        req_path = self.workspace_path / requirements_file
        
        if not req_path.exists():
            return vulnerabilities
        
        try:
            # Tentar usar pip-audit
            result = subprocess.run(
                ["pip-audit", "-r", str(req_path), "--format", "json"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                audit_results = json.loads(result.stdout)
                for dep in audit_results.get("dependencies", []):
                    for vuln in dep.get("vulns", []):
                        vuln_id = f"DEP-{self.scan_count:04d}"
                        self.scan_count += 1
                        
                        vulnerabilities.append(Vulnerability(
                            id=vuln_id,
                            type=VulnerabilityType.INSECURE_DEPENDENCY,
                            severity=self._map_severity(vuln.get("severity", "unknown")),
                            file_path=requirements_file,
                            line_number=0,
                            code_snippet=f"{dep.get('name')}=={dep.get('version')}",
                            description=vuln.get("description", "Vulnerabilidade conhecida em dependência"),
                            recommendation=f"Atualize para versão {vuln.get('fix_versions', ['latest'])[0] if vuln.get('fix_versions') else 'latest'}",
                            cwe_id=vuln.get("cwe_id"),
                            cvss_score=vuln.get("cvss_score")
                        ))
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            # pip-audit não disponível ou erro
            pass
        
        return vulnerabilities
    
    def generate_report_markdown(self, report: SecurityReport) -> str:
        """Gera relatório de segurança em Markdown"""
        md = f"""# 🔒 Relatório de Segurança

## Informações do Scan
| Campo | Valor |
|-------|-------|
| **Scan ID** | `{report.scan_id}` |
| **Data/Hora** | {report.timestamp} |
| **Alvo** | `{report.target}` |
| **Arquivos Escaneados** | {report.summary.get('files_scanned', 0)} |

## 📊 Sumário de Vulnerabilidades

| Severidade | Quantidade | Status |
|------------|------------|--------|
| 🔴 Critical | {report.summary.get('critical', 0)} | {'⛔ BLOQUEANTE' if report.summary.get('critical', 0) > 0 else '✅ OK'} |
| 🟠 High | {report.summary.get('high', 0)} | {'⚠️ ATENÇÃO' if report.summary.get('high', 0) > 0 else '✅ OK'} |
| 🟡 Medium | {report.summary.get('medium', 0)} | {'📋 Revisar' if report.summary.get('medium', 0) > 0 else '✅ OK'} |
| 🟢 Low | {report.summary.get('low', 0)} | {'📝 Informativo' if report.summary.get('low', 0) > 0 else '✅ OK'} |
| **Total** | **{report.summary.get('total_vulnerabilities', 0)}** | |

## ✅ Status de Compliance

| Framework | Status |
|-----------|--------|
| OWASP Top 10 | {'✅ Compliant' if report.compliance_status.get('owasp_compliant', True) else '❌ Non-Compliant'} |
| CWE/SANS Top 25 | {'✅ Compliant' if report.compliance_status.get('cwe_compliant', True) else '❌ Non-Compliant'} |
| Sem Secrets | {'✅ Compliant' if report.compliance_status.get('no_secrets', True) else '❌ Secrets Encontrados'} |

## 🔍 Vulnerabilidades Detalhadas

"""
        if not report.vulnerabilities:
            md += "_Nenhuma vulnerabilidade encontrada! 🎉_\n"
        else:
            # Agrupar por severidade
            for severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH, SeverityLevel.MEDIUM, SeverityLevel.LOW]:
                vulns = [v for v in report.vulnerabilities if v.severity == severity]
                if vulns:
                    emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}[severity.value]
                    md += f"\n### {emoji} {severity.value.upper()} ({len(vulns)})\n\n"
                    
                    for v in vulns:
                        md += f"""#### {v.id}: {v.type.value}
- **Arquivo:** `{v.file_path}:{v.line_number}`
- **CWE:** {v.cwe_id or 'N/A'}
- **CVSS:** {v.cvss_score or 'N/A'}
- **Descrição:** {v.description}
- **Código:**
{v.code_snippet}
- **Recomendação:** {v.recommendation}

---

"""
        
        md += f"""
## 📋 Próximos Passos

1. **Críticas/Altas:** Corrigir imediatamente antes do deploy
2. **Médias:** Planejar correção no próximo sprint
3. **Baixas:** Incluir no backlog de tech debt

---

_Gerado por SecurityAgent v{self.VERSION} | Eddie Auto-Dev_
"""
        
        return md
    
    def _mask_secret(self, line: str) -> str:
        """Mascara secrets no código para exibição segura"""
        # Substituir valores sensíveis por asteriscos
        masked = re.sub(r'(["\'])[^"\']{8,}(["\'])', r'\1****MASKED****\2', line)
        return masked[:100] + "..." if len(masked) > 100 else masked
    
    def _map_severity(self, severity_str: str) -> SeverityLevel:
        """Mapeia string de severidade para enum"""
        mapping = {
            "critical": SeverityLevel.CRITICAL,
            "high": SeverityLevel.HIGH,
            "medium": SeverityLevel.MEDIUM,
            "moderate": SeverityLevel.MEDIUM,
            "low": SeverityLevel.LOW,
            "info": SeverityLevel.INFO,
        }
        return mapping.get(severity_str.lower(), SeverityLevel.MEDIUM)
    
    def _check_compliance(self, vulnerabilities: List[Vulnerability]) -> Dict[str, bool]:
        """Verifica compliance com frameworks de segurança"""
        critical_types = {VulnerabilityType.SQL_INJECTION, VulnerabilityType.COMMAND_INJECTION}
        has_critical = any(v.type in critical_types for v in vulnerabilities)
        has_secrets = any(v.type == VulnerabilityType.HARDCODED_SECRET for v in vulnerabilities)
        
        return {
            "owasp_compliant": not has_critical,
            "cwe_compliant": not has_critical,
            "no_secrets": not has_secrets,
            "deployment_allowed": not (has_critical or has_secrets)
        }


# Exemplo de uso
if __name__ == "__main__":
    agent = SecurityAgent()
    
    print(f"SecurityAgent v{agent.VERSION}")
    print(f"Capabilities: {json.dumps(agent.capabilities, indent=2)}")
    print(f"\nRules inherited: {list(agent.AGENT_RULES.keys())}")
    
    # Executar scan
    report = agent.scan_directory()
    
    # Validar conforme Regra 0.2
    validation = agent.validate_scan(report)
    
    print(f"\nScan ID: {report.scan_id}")
    print(f"Files scanned: {report.summary.get('files_scanned', 0)}")
    print(f"Vulnerabilities: {report.summary.get('total_vulnerabilities', 0)}")
    print(f"Validation: {'✅ PASSED' if validation['valid'] else '❌ FAILED'}")
    
    if not validation['valid']:
        print(f"Reason: {validation.get('blocking_reason', 'Unknown')}")
