"""
Performance Agent para Shared Auto-Dev
Responsável por load testing, profiling, benchmarks e otimização

Versão: 1.0.0
Criado: 2025-01-16
Autor: Diretor Shared Auto-Dev
"""

import json
import time
import hashlib
import statistics
import asyncio
import aiohttp
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Memória persistente (opcional)
try:
    from .agent_memory import get_agent_memory
    _MEMORY_AVAILABLE = True
except Exception:
    _MEMORY_AVAILABLE = False


class TestType(Enum):
    """Tipos de testes de performance"""
    LOAD = "load"           # Carga progressiva
    STRESS = "stress"       # Até quebrar
    SPIKE = "spike"       # Picos de carga
    SOAK = "soak"           # Longa duração
    BENCHMARK = "benchmark" # Comparativo


class MetricType(Enum):
    """Tipos de métricas coletadas"""
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    LATENCY_P50 = "latency_p50"
    LATENCY_P95 = "latency_p95"
    LATENCY_P99 = "latency_p99"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    CONCURRENT_USERS = "concurrent_users"


@dataclass
class RequestResult:
    """Resultado de uma requisição"""
    url: str
    method: str
    status_code: int
    response_time: float  # ms
    content_length: int
    success: bool
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "url": self.url,
            "method": self.method,
            "status_code": self.status_code,
            "response_time": self.response_time,
            "content_length": self.content_length,
            "success": self.success,
            "error": self.error,
            "timestamp": self.timestamp
        }


@dataclass
class LoadTestConfig:
    """Configuração de teste de carga"""
    target_url: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None
    users: int = 10
    duration_seconds: int = 30
    ramp_up_seconds: int = 5
    test_type: TestType = TestType.LOAD
    
    def to_dict(self) -> Dict:
        return {
            "target_url": self.target_url,
            "method": self.method,
            "headers": self.headers,
            "body": self.body,
            "users": self.users,
            "duration_seconds": self.duration_seconds,
            "ramp_up_seconds": self.ramp_up_seconds,
            "test_type": self.test_type.value
        }


@dataclass
class PerformanceReport:
    """Relatório de performance"""
    test_id: str
    test_type: TestType
    config: LoadTestConfig
    started_at: str
    completed_at: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    metrics: Dict[str, float] = field(default_factory=dict)
    percentiles: Dict[str, float] = field(default_factory=dict)
    errors: Dict[str, int] = field(default_factory=dict)
    timeline: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "test_id": self.test_id,
            "test_type": self.test_type.value,
            "config": self.config.to_dict(),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "metrics": self.metrics,
            "percentiles": self.percentiles,
            "errors": self.errors,
            "timeline": self.timeline
        }


class PerformanceAgent:
    """
    Agent especializado em performance para Shared Auto-Dev.
    
    Responsabilidades:
    - Load Testing
    - Stress Testing
    - Benchmarking
    - Profiling de código
    - Análise de gargalos
    - Recomendações de otimização
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
            "format": "feat|fix|perf|refactor: descricao curta"
        },
        "communication": {
            "description": "Comunicar todas as ações via Communication Bus",
            "mandatory": True,
            "bus_integration": True
        },
        "performance_specific": {
            "description": "Regras específicas de performance",
            "mandatory": True,
            "baseline_required": True,
            "regression_threshold_percent": 10,
            "min_test_duration_seconds": 30,
            "warmup_requests": 100,
            "report_percentiles": [50, 95, 99]
        }
    }
    
    # Thresholds padrão
    DEFAULT_THRESHOLDS = {
        "response_time_ms": 500,      # < 500ms
        "error_rate_percent": 1,       # < 1%
        "throughput_rps": 100,         # > 100 req/s
        "latency_p99_ms": 2000         # < 2s
    }
    
    def __init__(self, workspace_path: str = "."):
        self.workspace_path = Path(workspace_path)
        self.reports_path = self.workspace_path / "performance_reports"
        self.reports_path.mkdir(exist_ok=True)
        self.test_count = 0
        self.baselines: Dict[str, Dict] = {}

        self.memory = None
        if _MEMORY_AVAILABLE:
            try:
                self.memory = get_agent_memory("performance_agent")
            except Exception as e:
                print(f"[Warning] Memória indisponível para PerformanceAgent: {e}")
        
        self.capabilities = {
            "name": "PerformanceAgent",
            "version": self.VERSION,
            "specialization": "Performance Engineering",
            "features": [
                "Load Testing",
                "Stress Testing",
                "Spike Testing",
                "Soak Testing",
                "Benchmarking",
                "Latency Analysis",
                "Throughput Measurement",
                "Percentile Calculation",
                "Baseline Comparison",
                "Performance Regression Detection"
            ],
            "test_types": [t.value for t in TestType],
            "metrics": [m.value for m in MetricType],
            "rules_inherited": list(self.AGENT_RULES.keys())
        }
    
    def get_rules(self) -> Dict[str, Any]:
        """Retorna as regras do agent conforme Regra 7"""
        return self.AGENT_RULES
    
    def validate_test(self, report: PerformanceReport, 
                      thresholds: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Valida o teste conforme Regra 0.2
        Compara métricas com thresholds
        """
        if thresholds is None:
            thresholds = self.DEFAULT_THRESHOLDS
        
        validation = {
            "valid": True,
            "timestamp": datetime.now().isoformat(),
            "test_id": report.test_id,
            "evidence": {
                "total_requests": report.total_requests,
                "success_rate": (report.successful_requests / report.total_requests * 100) 
                               if report.total_requests > 0 else 0,
                "avg_response_time": report.metrics.get("avg_response_time", 0),
                "throughput": report.metrics.get("throughput_rps", 0)
            },
            "checks": [],
            "passed": 0,
            "failed": 0
        }
        
        # Verificar response time
        avg_rt = report.metrics.get("avg_response_time", 0)
        if avg_rt <= thresholds.get("response_time_ms", 500):
            validation["checks"].append(f"✅ Response time: {avg_rt:.2f}ms <= {thresholds['response_time_ms']}ms")
            validation["passed"] += 1
        else:
            validation["checks"].append(f"❌ Response time: {avg_rt:.2f}ms > {thresholds['response_time_ms']}ms")
            validation["failed"] += 1
            validation["valid"] = False
        
        # Verificar error rate
        error_rate = (report.failed_requests / report.total_requests * 100) if report.total_requests > 0 else 0
        if error_rate <= thresholds.get("error_rate_percent", 1):
            validation["checks"].append(f"✅ Error rate: {error_rate:.2f}% <= {thresholds['error_rate_percent']}%")
            validation["passed"] += 1
        else:
            validation["checks"].append(f"❌ Error rate: {error_rate:.2f}% > {thresholds['error_rate_percent']}%")
            validation["failed"] += 1
            validation["valid"] = False
        
        # Verificar throughput
        throughput = report.metrics.get("throughput_rps", 0)
        if throughput >= thresholds.get("throughput_rps", 100):
            validation["checks"].append(f"✅ Throughput: {throughput:.2f} rps >= {thresholds['throughput_rps']} rps")
            validation["passed"] += 1
        else:
            validation["checks"].append(f"⚠️ Throughput: {throughput:.2f} rps < {thresholds['throughput_rps']} rps")
            # Não falha, apenas warning
        
        # Verificar P99
        p99 = report.percentiles.get("p99", 0)
        if p99 <= thresholds.get("latency_p99_ms", 2000):
            validation["checks"].append(f"✅ P99 Latency: {p99:.2f}ms <= {thresholds['latency_p99_ms']}ms")
            validation["passed"] += 1
        else:
            validation["checks"].append(f"❌ P99 Latency: {p99:.2f}ms > {thresholds['latency_p99_ms']}ms")
            validation["failed"] += 1
            validation["valid"] = False
        
        return validation
    
    def generate_test_id(self, target: str) -> str:
        """Gera ID único para teste"""
        self.test_count += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"perf_{timestamp}_{self.test_count:04d}"
    
    async def _make_request(self, session: aiohttp.ClientSession, 
                            config: LoadTestConfig) -> RequestResult:
        """Faz uma requisição HTTP"""
        start_time = time.time()
        
        try:
            async with session.request(
                method=config.method,
                url=config.target_url,
                headers=config.headers,
                data=config.body,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                content = await response.read()
                elapsed = (time.time() - start_time) * 1000  # ms
                
                return RequestResult(
                    url=config.target_url,
                    method=config.method,
                    status_code=response.status,
                    response_time=elapsed,
                    content_length=len(content),
                    success=200 <= response.status < 400
                )
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return RequestResult(
                url=config.target_url,
                method=config.method,
                status_code=0,
                response_time=elapsed,
                content_length=0,
                success=False,
                error=str(e)
            )
    
    async def _run_load_test_async(self, config: LoadTestConfig) -> List[RequestResult]:
        """Executa teste de carga assíncrono"""
        results = []
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            # Warmup
            warmup_count = self.AGENT_RULES["performance_specific"]["warmup_requests"]
            warmup_tasks = [self._make_request(session, config) for _ in range(min(warmup_count, 10))]
            await asyncio.gather(*warmup_tasks)
            
            # Teste principal
            current_users = 0
            ramp_up_per_second = config.users / config.ramp_up_seconds if config.ramp_up_seconds > 0 else config.users
            
            while time.time() - start_time < config.duration_seconds:
                elapsed = time.time() - start_time
                
                # Ramp up
                if elapsed < config.ramp_up_seconds:
                    current_users = int(elapsed * ramp_up_per_second) + 1
                else:
                    current_users = config.users
                
                # Criar tasks para usuários concorrentes
                tasks = [self._make_request(session, config) for _ in range(current_users)]
                batch_results = await asyncio.gather(*tasks)
                results.extend(batch_results)
                
                # Pequena pausa para não sobrecarregar
                await asyncio.sleep(0.1)
        
        return results
    
    def run_load_test(self, config: LoadTestConfig) -> PerformanceReport:
        """Executa teste de carga"""
        test_id = self.generate_test_id(config.target_url)
        started_at = datetime.now().isoformat()
        
        # Executar teste assíncrono
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        results = loop.run_until_complete(self._run_load_test_async(config))
        
        completed_at = datetime.now().isoformat()
        
        # Calcular métricas
        response_times = [r.response_time for r in results]
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        # Agrupar erros
        errors = {}
        for r in failed:
            error_key = r.error or f"HTTP {r.status_code}"
            errors[error_key] = errors.get(error_key, 0) + 1
        
        # Calcular percentis
        sorted_times = sorted(response_times)
        percentiles = {}
        if sorted_times:
            percentiles["p50"] = self._percentile(sorted_times, 50)
            percentiles["p95"] = self._percentile(sorted_times, 95)
            percentiles["p99"] = self._percentile(sorted_times, 99)
        
        # Calcular throughput
        duration = config.duration_seconds
        throughput = len(results) / duration if duration > 0 else 0
        
        metrics = {
            "avg_response_time": statistics.mean(response_times) if response_times else 0,
            "min_response_time": min(response_times) if response_times else 0,
            "max_response_time": max(response_times) if response_times else 0,
            "std_dev": statistics.stdev(response_times) if len(response_times) > 1 else 0,
            "throughput_rps": throughput,
            "success_rate": len(successful) / len(results) * 100 if results else 0
        }
        
        # Timeline (amostragem)
        timeline = []
        sample_size = min(100, len(results))
        step = len(results) // sample_size if sample_size > 0 else 1
        for i in range(0, len(results), max(1, step)):
            timeline.append({
                "index": i,
                "response_time": results[i].response_time,
                "success": results[i].success
            })
        
        report = PerformanceReport(
            test_id=test_id,
            test_type=config.test_type,
            config=config,
            started_at=started_at,
            completed_at=completed_at,
            total_requests=len(results),
            successful_requests=len(successful),
            failed_requests=len(failed),
            metrics=metrics,
            percentiles=percentiles,
            errors=errors,
            timeline=timeline
        )
        
        # Salvar relatório
        report_path = self.reports_path / f"{test_id}.json"
        with open(report_path, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
        
        return report
    
    def run_benchmark(self, functions: Dict[str, Callable], 
                      iterations: int = 1000) -> Dict[str, Any]:
        """Executa benchmark comparativo de funções"""
        results = {}
        
        for name, func in functions.items():
            times = []
            
            # Warmup
            for _ in range(10):
                func()
            
            # Benchmark
            for _ in range(iterations):
                start = time.perf_counter()
                func()
                elapsed = (time.perf_counter() - start) * 1000  # ms
                times.append(elapsed)
            
            results[name] = {
                "iterations": iterations,
                "avg_ms": statistics.mean(times),
                "min_ms": min(times),
                "max_ms": max(times),
                "std_dev_ms": statistics.stdev(times) if len(times) > 1 else 0,
                "p50_ms": self._percentile(sorted(times), 50),
                "p95_ms": self._percentile(sorted(times), 95),
                "p99_ms": self._percentile(sorted(times), 99),
                "ops_per_sec": 1000 / statistics.mean(times) if statistics.mean(times) > 0 else 0
            }
        
        # Ranking
        ranking = sorted(results.items(), key=lambda x: x[1]["avg_ms"])
        
        return {
            "benchmark_id": self.generate_test_id("benchmark"),
            "timestamp": datetime.now().isoformat(),
            "iterations": iterations,
            "results": results,
            "ranking": [{"rank": i+1, "name": name, "avg_ms": data["avg_ms"]} 
                       for i, (name, data) in enumerate(ranking)]
        }
    
    def set_baseline(self, endpoint: str, report: PerformanceReport):
        """Define baseline de performance para um endpoint"""
        self.baselines[endpoint] = {
            "test_id": report.test_id,
            "timestamp": report.completed_at,
            "metrics": report.metrics.copy(),
            "percentiles": report.percentiles.copy()
        }
    
    def check_regression(self, endpoint: str, 
                         report: PerformanceReport) -> Dict[str, Any]:
        """Verifica regressão de performance contra baseline"""
        if endpoint not in self.baselines:
            return {
                "has_baseline": False,
                "message": "Nenhum baseline definido para este endpoint"
            }
        
        baseline = self.baselines[endpoint]
        threshold = self.AGENT_RULES["performance_specific"]["regression_threshold_percent"]
        
        regressions = []
        improvements = []
        
        for metric, baseline_value in baseline["metrics"].items():
            if baseline_value == 0:
                continue
            
            current_value = report.metrics.get(metric, 0)
            change_percent = ((current_value - baseline_value) / baseline_value) * 100
            
            # Para response time, aumento é ruim
            if "response_time" in metric or "latency" in metric:
                if change_percent > threshold:
                    regressions.append({
                        "metric": metric,
                        "baseline": baseline_value,
                        "current": current_value,
                        "change_percent": change_percent
                    })
                elif change_percent < -threshold:
                    improvements.append({
                        "metric": metric,
                        "baseline": baseline_value,
                        "current": current_value,
                        "change_percent": change_percent
                    })
            # Para throughput, diminuição é ruim
            elif "throughput" in metric:
                if change_percent < -threshold:
                    regressions.append({
                        "metric": metric,
                        "baseline": baseline_value,
                        "current": current_value,
                        "change_percent": change_percent
                    })
                elif change_percent > threshold:
                    improvements.append({
                        "metric": metric,
                        "baseline": baseline_value,
                        "current": current_value,
                        "change_percent": change_percent
                    })
        
        return {
            "has_baseline": True,
            "baseline_test_id": baseline["test_id"],
            "has_regression": len(regressions) > 0,
            "regressions": regressions,
            "improvements": improvements,
            "threshold_percent": threshold
        }
    
    def generate_report_markdown(self, report: PerformanceReport) -> str:
        """Gera relatório de performance em Markdown"""
        validation = self.validate_test(report)
        
        md = f"""# ⚡ Relatório de Performance

## Informações do Teste
| Campo | Valor |
|-------|-------|
| **Test ID** | `{report.test_id}` |
| **Tipo** | {report.test_type.value} |
| **Target** | `{report.config.target_url}` |
| **Usuários** | {report.config.users} |
| **Duração** | {report.config.duration_seconds}s |
| **Início** | {report.started_at} |
| **Fim** | {report.completed_at} |

## 📊 Sumário de Requisições

| Métrica | Valor |
|---------|-------|
| **Total** | {report.total_requests:,} |
| **Sucesso** | {report.successful_requests:,} ({report.metrics.get('success_rate', 0):.1f}%) |
| **Falha** | {report.failed_requests:,} |
| **Throughput** | {report.metrics.get('throughput_rps', 0):.2f} req/s |

## ⏱️ Latência (Response Time)

| Percentil | Valor |
|-----------|-------|
| **Média** | {report.metrics.get('avg_response_time', 0):.2f} ms |
| **Min** | {report.metrics.get('min_response_time', 0):.2f} ms |
| **Max** | {report.metrics.get('max_response_time', 0):.2f} ms |
| **Std Dev** | {report.metrics.get('std_dev', 0):.2f} ms |
| **P50** | {report.percentiles.get('p50', 0):.2f} ms |
| **P95** | {report.percentiles.get('p95', 0):.2f} ms |
| **P99** | {report.percentiles.get('p99', 0):.2f} ms |

## ✅ Validação

| Status | {'✅ PASSED' if validation['valid'] else '❌ FAILED'} |
|--------|--------|
| **Checks Passed** | {validation['passed']} |
| **Checks Failed** | {validation['failed']} |

### Detalhes dos Checks
"""
        for check in validation["checks"]:
            md += f"- {check}\n"
        
        if report.errors:
            md += "\n## ❌ Erros Encontrados\n\n"
            md += "| Erro | Quantidade |\n|------|------------|\n"
            for error, count in report.errors.items():
                md += f"| {error[:50]} | {count} |\n"
        
        md += f"""

## 📈 Recomendações

"""
        if report.metrics.get('avg_response_time', 0) > 500:
            md += "- ⚠️ **Response time alto**: Considere otimizar queries ou adicionar cache\n"
        
        if report.metrics.get('success_rate', 100) < 99:
            md += "- ⚠️ **Taxa de erro elevada**: Investigar erros e implementar retry logic\n"
        
        if report.percentiles.get('p99', 0) > 2000:
            md += "- ⚠️ **P99 muito alto**: Identificar outliers e otimizar casos extremos\n"
        
        if report.metrics.get('throughput_rps', 0) < 100:
            md += "- 💡 **Throughput baixo**: Considere escalar horizontalmente ou otimizar código\n"
        
        md += f"""

---

_Gerado por PerformanceAgent v{self.VERSION} | Shared Auto-Dev_
"""
        
        return md
    
    def _percentile(self, data: List[float], p: int) -> float:
        """Calcula percentil"""
        if not data:
            return 0
        k = (len(data) - 1) * (p / 100)
        f = int(k)
        c = f + 1 if f + 1 < len(data) else f
        return data[f] + (k - f) * (data[c] - data[f]) if f != c else data[f]


# Singleton
_performance_agent: Optional[PerformanceAgent] = None

def get_performance_agent(workspace_path: str = ".") -> PerformanceAgent:
    """Retorna instância singleton do PerformanceAgent"""
    global _performance_agent
    if _performance_agent is None:
        _performance_agent = PerformanceAgent(workspace_path)
    return _performance_agent


# Exemplo de uso
if __name__ == "__main__":
    agent = PerformanceAgent()
    
    print(f"PerformanceAgent v{agent.VERSION}")
    print(f"Capabilities: {json.dumps(agent.capabilities, indent=2)}")
    print(f"\nRules inherited: {list(agent.AGENT_RULES.keys())}")
    print(f"Default thresholds: {agent.DEFAULT_THRESHOLDS}")
