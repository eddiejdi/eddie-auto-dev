"""
Data Agent para Eddie Auto-Dev
Responsável por ETL, pipelines de dados, analytics e transformações

Versão: 1.0.0
Criado: 2025-01-16
Autor: Diretor Eddie Auto-Dev
"""

import json
import hashlib
import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import re

# Memória persistente (opcional)
try:
    from .agent_memory import get_agent_memory
    _MEMORY_AVAILABLE = True
except Exception:
    _MEMORY_AVAILABLE = False


class DataFormat(Enum):
    """Formatos de dados suportados"""
    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"
    SQLITE = "sqlite"
    YAML = "yaml"
    XML = "xml"
    EXCEL = "excel"


class TransformationType(Enum):
    """Tipos de transformações disponíveis"""
    FILTER = "filter"
    MAP = "map"
    AGGREGATE = "aggregate"
    JOIN = "join"
    SORT = "sort"
    DEDUPLICATE = "deduplicate"
    NORMALIZE = "normalize"
    PIVOT = "pivot"
    UNPIVOT = "unpivot"
    VALIDATE = "validate"


@dataclass
class DataSource:
    """Representa uma fonte de dados"""
    name: str
    format: DataFormat
    path: str
    schema: Optional[Dict[str, str]] = None
    row_count: int = 0
    last_updated: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "format": self.format.value,
            "path": self.path,
            "schema": self.schema,
            "row_count": self.row_count,
            "last_updated": self.last_updated
        }


@dataclass
class PipelineStep:
    """Representa um passo no pipeline"""
    id: str
    type: TransformationType
    config: Dict[str, Any]
    input_source: str
    output_name: str
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "config": self.config,
            "input_source": self.input_source,
            "output_name": self.output_name
        }


@dataclass
class Pipeline:
    """Representa um pipeline de dados completo"""
    id: str
    name: str
    description: str
    steps: List[PipelineStep] = field(default_factory=list)
    sources: List[DataSource] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_run: Optional[str] = None
    status: str = "created"
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "sources": [s.to_dict() for s in self.sources],
            "created_at": self.created_at,
            "last_run": self.last_run,
            "status": self.status
        }


@dataclass
class DataQualityReport:
    """Relatório de qualidade de dados"""
    source_name: str
    timestamp: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    null_counts: Dict[str, int] = field(default_factory=dict)
    duplicate_count: int = 0
    issues: List[str] = field(default_factory=list)
    score: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "source_name": self.source_name,
            "timestamp": self.timestamp,
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "invalid_rows": self.invalid_rows,
            "null_counts": self.null_counts,
            "duplicate_count": self.duplicate_count,
            "issues": self.issues,
            "score": self.score
        }


class DataAgent:
    """
    Agent especializado em dados para Eddie Auto-Dev.
    
    Responsabilidades:
    - ETL (Extract, Transform, Load)
    - Pipelines de dados
    - Analytics e métricas
    - Qualidade de dados
    - Transformações e agregações
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
            "format": "feat|fix|data|refactor: descricao curta"
        },
        "communication": {
            "description": "Comunicar todas as ações via Communication Bus",
            "mandatory": True,
            "bus_integration": True
        },
        "data_specific": {
            "description": "Regras específicas de dados",
            "mandatory": True,
            "validate_schema": True,
            "check_data_quality": True,
            "log_transformations": True,
            "backup_before_transform": True,
            "idempotent_pipelines": True
        }
    }
    
    def __init__(self, workspace_path: str = "."):
        self.workspace_path = Path(workspace_path)
        self.data_path = self.workspace_path / "data"
        self.data_path.mkdir(exist_ok=True)
        self.pipelines: Dict[str, Pipeline] = {}
        self.sources: Dict[str, DataSource] = {}
        self.step_count = 0

        self.memory = None
        if _MEMORY_AVAILABLE:
            try:
                self.memory = get_agent_memory("data_agent")
            except Exception as e:
                print(f"[Warning] Memória indisponível para DataAgent: {e}")
        
        self.capabilities = {
            "name": "DataAgent",
            "version": self.VERSION,
            "specialization": "Data Engineering",
            "features": [
                "ETL (Extract, Transform, Load)",
                "Data Pipeline Management",
                "Data Quality Assessment",
                "Schema Validation",
                "Data Transformations",
                "Analytics & Metrics",
                "Format Conversion"
            ],
            "supported_formats": [f.value for f in DataFormat],
            "transformations": [t.value for t in TransformationType],
            "rules_inherited": list(self.AGENT_RULES.keys())
        }
    
    def get_rules(self) -> Dict[str, Any]:
        """Retorna as regras do agent conforme Regra 7"""
        return self.AGENT_RULES
    
    def validate_pipeline(self, pipeline: Pipeline) -> Dict[str, Any]:
        """
        Valida o pipeline conforme Regra 0.2
        Retorna evidências da validação
        """
        validation = {
            "valid": True,
            "timestamp": datetime.now().isoformat(),
            "pipeline_id": pipeline.id,
            "evidence": {
                "steps_count": len(pipeline.steps),
                "sources_count": len(pipeline.sources),
                "status": pipeline.status
            },
            "checks": []
        }
        
        # Verificar se há pelo menos uma fonte
        if not pipeline.sources:
            validation["valid"] = False
            validation["checks"].append("❌ Pipeline não tem fontes de dados")
        else:
            validation["checks"].append(f"✅ {len(pipeline.sources)} fontes configuradas")
        
        # Verificar se há pelo menos um step
        if not pipeline.steps:
            validation["valid"] = False
            validation["checks"].append("❌ Pipeline não tem steps de transformação")
        else:
            validation["checks"].append(f"✅ {len(pipeline.steps)} steps configurados")
        
        # Verificar dependências entre steps
        output_names = set()
        for step in pipeline.steps:
            if step.input_source not in output_names and step.input_source not in [s.name for s in pipeline.sources]:
                validation["valid"] = False
                validation["checks"].append(f"❌ Step {step.id}: fonte '{step.input_source}' não encontrada")
            output_names.add(step.output_name)
        
        if validation["valid"]:
            validation["checks"].append("✅ Todas as dependências resolvidas")
        
        return validation
    
    def generate_pipeline_id(self, name: str) -> str:
        """Gera ID único para pipeline"""
        timestamp = datetime.now().isoformat()
        content = f"{name}-{timestamp}"
        return f"pipe_{hashlib.sha256(content.encode()).hexdigest()[:8]}"
    
    def create_pipeline(self, name: str, description: str = "") -> Pipeline:
        """Cria um novo pipeline de dados"""
        pipeline_id = self.generate_pipeline_id(name)
        pipeline = Pipeline(
            id=pipeline_id,
            name=name,
            description=description
        )
        self.pipelines[pipeline_id] = pipeline
        return pipeline
    
    def add_source(self, pipeline_id: str, name: str, 
                   format: DataFormat, path: str,
                   schema: Optional[Dict[str, str]] = None) -> DataSource:
        """Adiciona fonte de dados ao pipeline"""
        if pipeline_id not in self.pipelines:
            raise ValueError(f"Pipeline {pipeline_id} não encontrado")
        
        source = DataSource(
            name=name,
            format=format,
            path=path,
            schema=schema,
            last_updated=datetime.now().isoformat()
        )
        
        # Tentar inferir row_count
        source.row_count = self._count_rows(source)
        
        self.pipelines[pipeline_id].sources.append(source)
        self.sources[name] = source
        return source
    
    def add_step(self, pipeline_id: str, 
                 transform_type: TransformationType,
                 config: Dict[str, Any],
                 input_source: str,
                 output_name: str) -> PipelineStep:
        """Adiciona step de transformação ao pipeline"""
        if pipeline_id not in self.pipelines:
            raise ValueError(f"Pipeline {pipeline_id} não encontrado")
        
        self.step_count += 1
        step_id = f"step_{self.step_count:04d}"
        
        step = PipelineStep(
            id=step_id,
            type=transform_type,
            config=config,
            input_source=input_source,
            output_name=output_name
        )
        
        self.pipelines[pipeline_id].steps.append(step)
        return step
    
    def run_pipeline(self, pipeline_id: str) -> Dict[str, Any]:
        """Executa um pipeline de dados"""
        if pipeline_id not in self.pipelines:
            raise ValueError(f"Pipeline {pipeline_id} não encontrado")
        
        pipeline = self.pipelines[pipeline_id]
        
        # Validar antes de executar (Regra 0.2)
        validation = self.validate_pipeline(pipeline)
        if not validation["valid"]:
            return {
                "success": False,
                "error": "Pipeline validation failed",
                "validation": validation
            }
        
        pipeline.status = "running"
        pipeline.last_run = datetime.now().isoformat()
        
        results = {
            "pipeline_id": pipeline_id,
            "started_at": pipeline.last_run,
            "steps_executed": [],
            "success": True
        }
        
        # Executar cada step
        data_cache = {}
        
        # Carregar fontes
        for source in pipeline.sources:
            try:
                data_cache[source.name] = self._load_source(source)
                results["steps_executed"].append({
                    "type": "load",
                    "source": source.name,
                    "rows": len(data_cache[source.name]),
                    "status": "success"
                })
            except Exception as e:
                results["success"] = False
                results["error"] = f"Erro ao carregar {source.name}: {str(e)}"
                pipeline.status = "failed"
                return results
        
        # Executar transformações
        for step in pipeline.steps:
            try:
                input_data = data_cache.get(step.input_source, [])
                output_data = self._execute_transform(step, input_data)
                data_cache[step.output_name] = output_data
                
                results["steps_executed"].append({
                    "step_id": step.id,
                    "type": step.type.value,
                    "input_rows": len(input_data),
                    "output_rows": len(output_data),
                    "status": "success"
                })
            except Exception as e:
                results["success"] = False
                results["error"] = f"Erro no step {step.id}: {str(e)}"
                pipeline.status = "failed"
                return results
        
        pipeline.status = "completed"
        results["completed_at"] = datetime.now().isoformat()
        
        return results
    
    def assess_data_quality(self, source_name: str) -> DataQualityReport:
        """Avalia qualidade dos dados de uma fonte"""
        if source_name not in self.sources:
            raise ValueError(f"Fonte {source_name} não encontrada")
        
        source = self.sources[source_name]
        data = self._load_source(source)
        
        total_rows = len(data)
        null_counts = {}
        issues = []
        invalid_rows = 0
        
        if total_rows == 0:
            return DataQualityReport(
                source_name=source_name,
                timestamp=datetime.now().isoformat(),
                total_rows=0,
                valid_rows=0,
                invalid_rows=0,
                score=0.0,
                issues=["Fonte de dados vazia"]
            )
        
        # Analisar colunas (assumindo dados como lista de dicts)
        if isinstance(data[0], dict):
            columns = list(data[0].keys())
            
            for col in columns:
                null_count = sum(1 for row in data if row.get(col) is None or row.get(col) == "")
                null_counts[col] = null_count
                
                if null_count > total_rows * 0.5:
                    issues.append(f"Coluna '{col}' tem mais de 50% de valores nulos")
        
        # Verificar duplicatas
        try:
            seen = set()
            duplicate_count = 0
            for row in data:
                row_hash = hash(json.dumps(row, sort_keys=True, default=str))
                if row_hash in seen:
                    duplicate_count += 1
                seen.add(row_hash)
        except:
            duplicate_count = 0
        
        if duplicate_count > 0:
            issues.append(f"Encontradas {duplicate_count} linhas duplicadas")
        
        # Calcular score de qualidade
        null_penalty = sum(null_counts.values()) / (total_rows * len(null_counts)) if null_counts else 0
        dup_penalty = duplicate_count / total_rows if total_rows > 0 else 0
        score = max(0, 100 - (null_penalty * 50) - (dup_penalty * 30))
        
        valid_rows = total_rows - invalid_rows
        
        return DataQualityReport(
            source_name=source_name,
            timestamp=datetime.now().isoformat(),
            total_rows=total_rows,
            valid_rows=valid_rows,
            invalid_rows=invalid_rows,
            null_counts=null_counts,
            duplicate_count=duplicate_count,
            issues=issues,
            score=round(score, 2)
        )
    
    def convert_format(self, input_path: str, output_path: str,
                       input_format: DataFormat, output_format: DataFormat) -> Dict[str, Any]:
        """Converte dados entre formatos"""
        source = DataSource(
            name="temp_convert",
            format=input_format,
            path=input_path
        )
        
        data = self._load_source(source)
        
        output_path = Path(output_path)
        
        if output_format == DataFormat.JSON:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        
        elif output_format == DataFormat.CSV:
            if data and isinstance(data[0], dict):
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
        
        elif output_format == DataFormat.SQLITE:
            conn = sqlite3.connect(str(output_path))
            if data and isinstance(data[0], dict):
                columns = list(data[0].keys())
                table_name = "data"
                
                # Criar tabela
                col_defs = ", ".join([f'"{c}" TEXT' for c in columns])
                conn.execute(f'CREATE TABLE IF NOT EXISTS {table_name} ({col_defs})')
                
                # Inserir dados
                placeholders = ", ".join(["?" for _ in columns])
                for row in data:
                    values = [str(row.get(c, "")) for c in columns]
                    conn.execute(f'INSERT INTO {table_name} VALUES ({placeholders})', values)
                
                conn.commit()
            conn.close()
        
        return {
            "success": True,
            "input_format": input_format.value,
            "output_format": output_format.value,
            "rows_converted": len(data),
            "output_path": str(output_path)
        }
    
    def generate_metrics(self, source_name: str) -> Dict[str, Any]:
        """Gera métricas analíticas de uma fonte de dados"""
        if source_name not in self.sources:
            raise ValueError(f"Fonte {source_name} não encontrada")
        
        source = self.sources[source_name]
        data = self._load_source(source)
        
        metrics = {
            "source_name": source_name,
            "timestamp": datetime.now().isoformat(),
            "row_count": len(data),
            "columns": {},
            "summary": {}
        }
        
        if not data:
            return metrics
        
        if isinstance(data[0], dict):
            columns = list(data[0].keys())
            metrics["column_count"] = len(columns)
            
            for col in columns:
                values = [row.get(col) for row in data if row.get(col) is not None]
                col_metrics = {
                    "non_null_count": len(values),
                    "null_count": len(data) - len(values),
                    "unique_count": len(set(str(v) for v in values))
                }
                
                # Tentar métricas numéricas
                try:
                    numeric_values = [float(v) for v in values if v is not None]
                    if numeric_values:
                        col_metrics["min"] = min(numeric_values)
                        col_metrics["max"] = max(numeric_values)
                        col_metrics["avg"] = sum(numeric_values) / len(numeric_values)
                        col_metrics["sum"] = sum(numeric_values)
                except (ValueError, TypeError):
                    pass
                
                metrics["columns"][col] = col_metrics
        
        return metrics
    
    def _load_source(self, source: DataSource) -> List[Dict]:
        """Carrega dados de uma fonte"""
        path = Path(source.path)
        
        if not path.exists():
            # Se não existe, retornar lista vazia ou criar sample
            return []
        
        if source.format == DataFormat.JSON:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else [data]
        
        elif source.format == DataFormat.CSV:
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                return list(reader)
        
        elif source.format == DataFormat.SQLITE:
            conn = sqlite3.connect(str(path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            table = cursor.fetchone()
            if table:
                cursor.execute(f"SELECT * FROM {table[0]}")
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            conn.close()
            return []
        
        return []
    
    def _count_rows(self, source: DataSource) -> int:
        """Conta linhas em uma fonte"""
        try:
            data = self._load_source(source)
            return len(data)
        except:
            return 0
    
    def _execute_transform(self, step: PipelineStep, data: List[Dict]) -> List[Dict]:
        """Executa uma transformação"""
        if step.type == TransformationType.FILTER:
            field = step.config.get("field")
            operator = step.config.get("operator", "eq")
            value = step.config.get("value")
            
            if operator == "eq":
                return [row for row in data if row.get(field) == value]
            elif operator == "ne":
                return [row for row in data if row.get(field) != value]
            elif operator == "gt":
                return [row for row in data if row.get(field, 0) > value]
            elif operator == "lt":
                return [row for row in data if row.get(field, 0) < value]
            elif operator == "contains":
                return [row for row in data if value in str(row.get(field, ""))]
        
        elif step.type == TransformationType.MAP:
            new_field = step.config.get("new_field")
            expression = step.config.get("expression")
            
            result = []
            for row in data:
                new_row = row.copy()
                # Simples expressão: field1 + field2
                try:
                    new_row[new_field] = eval(expression, {"row": row, "__builtins__": {}})
                except:
                    new_row[new_field] = None
                result.append(new_row)
            return result
        
        elif step.type == TransformationType.SORT:
            field = step.config.get("field")
            reverse = step.config.get("descending", False)
            return sorted(data, key=lambda x: x.get(field, ""), reverse=reverse)
        
        elif step.type == TransformationType.DEDUPLICATE:
            fields = step.config.get("fields", [])
            seen = set()
            result = []
            for row in data:
                key = tuple(row.get(f) for f in fields) if fields else tuple(row.values())
                if key not in seen:
                    seen.add(key)
                    result.append(row)
            return result
        
        elif step.type == TransformationType.AGGREGATE:
            group_by = step.config.get("group_by", [])
            aggregations = step.config.get("aggregations", {})
            
            groups = {}
            for row in data:
                key = tuple(row.get(f) for f in group_by)
                if key not in groups:
                    groups[key] = []
                groups[key].append(row)
            
            result = []
            for key, rows in groups.items():
                agg_row = dict(zip(group_by, key))
                for agg_name, agg_config in aggregations.items():
                    field = agg_config.get("field")
                    func = agg_config.get("func", "count")
                    values = [r.get(field) for r in rows if r.get(field) is not None]
                    
                    if func == "count":
                        agg_row[agg_name] = len(values)
                    elif func == "sum":
                        agg_row[agg_name] = sum(float(v) for v in values)
                    elif func == "avg":
                        agg_row[agg_name] = sum(float(v) for v in values) / len(values) if values else 0
                    elif func == "min":
                        agg_row[agg_name] = min(values) if values else None
                    elif func == "max":
                        agg_row[agg_name] = max(values) if values else None
                
                result.append(agg_row)
            return result
        
        return data


# Singleton
_data_agent: Optional[DataAgent] = None

def get_data_agent(workspace_path: str = ".") -> DataAgent:
    """Retorna instância singleton do DataAgent"""
    global _data_agent
    if _data_agent is None:
        _data_agent = DataAgent(workspace_path)
    return _data_agent


# Exemplo de uso
if __name__ == "__main__":
    agent = DataAgent()
    
    print(f"DataAgent v{agent.VERSION}")
    print(f"Capabilities: {json.dumps(agent.capabilities, indent=2)}")
    print(f"\nRules inherited: {list(agent.AGENT_RULES.keys())}")
    
    # Criar pipeline de exemplo
    pipeline = agent.create_pipeline(
        name="test_pipeline",
        description="Pipeline de teste"
    )
    
    print(f"\nPipeline criado: {pipeline.id}")
    
    # Validar
    validation = agent.validate_pipeline(pipeline)
    print(f"Validação: {validation}")
