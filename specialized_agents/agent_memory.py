#!/usr/bin/env python3
"""
Agent Memory System - Memória Persistente para Agentes
Permite que agentes lembrem de decisões passadas e aprendam com experiências anteriores.
"""
import os
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

# psycopg2 is optional; tests and other code shouldn't fail if it's missing.
try:
    import psycopg2
    import psycopg2.extras
except ImportError:  # pragma: no cover
    psycopg2 = None
    psycopg2_extras = None

DATABASE_URL = os.environ.get('DATABASE_URL')


class AgentMemory:
    """
    Sistema de memória persistente para agentes.
    Armazena decisões, contextos e resultados para aprendizado incremental.
    """
    
    def __init__(self, agent_name: str, db_url: str = None):
        self.agent_name = agent_name
        self.db_url = db_url or DATABASE_URL
        if not self.db_url:
            raise RuntimeError('DATABASE_URL not set for AgentMemory')
        self._init_tables()
    
    def _get_conn(self):
        """Obtém conexão com o banco"""
        if psycopg2 is None:
            raise RuntimeError("psycopg2 not installed; agent memory unavailable")
        return psycopg2.connect(self.db_url)
    
    def _init_tables(self):
        """Inicializa tabelas de memória"""
        sql = '''
        -- Tabela principal de memória de decisões
        CREATE TABLE IF NOT EXISTS agent_memory (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            agent_name TEXT NOT NULL,
            
            -- Contexto da decisão
            application TEXT,
            component TEXT,
            error_type TEXT,
            error_signature TEXT,  -- hash do erro para busca rápida
            context_data JSONB,
            
            -- Decisão tomada
            decision_type TEXT NOT NULL,  -- deploy, reject, fix, analyze
            decision TEXT NOT NULL,
            reasoning TEXT,
            confidence FLOAT DEFAULT 0.5,
            
            -- Resultado da decisão
            outcome TEXT,  -- success, failure, unknown
            outcome_details JSONB,
            feedback_score FLOAT,
            
            -- Metadata
            metadata JSONB DEFAULT '{}'::jsonb
        );
        
        -- Índices para busca eficiente
        CREATE INDEX IF NOT EXISTS idx_agent_memory_agent ON agent_memory(agent_name);
        CREATE INDEX IF NOT EXISTS idx_agent_memory_app_comp ON agent_memory(application, component);
        CREATE INDEX IF NOT EXISTS idx_agent_memory_error_sig ON agent_memory(error_signature);
        CREATE INDEX IF NOT EXISTS idx_agent_memory_decision ON agent_memory(decision_type);
        CREATE INDEX IF NOT EXISTS idx_agent_memory_created ON agent_memory(created_at DESC);
        
        -- Tabela de padrões aprendidos
        CREATE TABLE IF NOT EXISTS agent_learned_patterns (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            agent_name TEXT NOT NULL,
            
            pattern_type TEXT NOT NULL,
            pattern_signature TEXT UNIQUE NOT NULL,
            pattern_data JSONB NOT NULL,
            
            occurrences INT DEFAULT 1,
            success_count INT DEFAULT 0,
            failure_count INT DEFAULT 0,
            confidence FLOAT DEFAULT 0.5,
            
            last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT now()
        );
        
        CREATE INDEX IF NOT EXISTS idx_learned_patterns_agent ON agent_learned_patterns(agent_name);
        CREATE INDEX IF NOT EXISTS idx_learned_patterns_sig ON agent_learned_patterns(pattern_signature);
        '''
        
        conn = self._get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
        finally:
            conn.close()
    
    def _generate_error_signature(self, error_type: str, error_message: str, 
                                   application: str = None, component: str = None) -> str:
        """Gera assinatura única para um erro"""
        signature_data = f"{application}:{component}:{error_type}:{error_message[:200]}"
        return hashlib.sha256(signature_data.encode()).hexdigest()[:16]
    
    def record_decision(
        self,
        application: str,
        component: str,
        error_type: str,
        error_message: str,
        decision_type: str,
        decision: str,
        reasoning: str = None,
        confidence: float = 0.5,
        context_data: Dict = None,
        metadata: Dict = None
    ) -> int:
        """
        Registra uma decisão tomada pelo agente.
        
        Args:
            application: Nome da aplicação
            component: Componente específico
            error_type: Tipo de erro encontrado
            error_message: Mensagem de erro
            decision_type: Tipo de decisão (deploy, reject, fix, analyze)
            decision: Decisão tomada
            reasoning: Raciocínio por trás da decisão
            confidence: Nível de confiança (0.0-1.0)
            context_data: Dados adicionais de contexto
            metadata: Metadados adicionais
            
        Returns:
            ID do registro criado
        """
        error_sig = self._generate_error_signature(error_type, error_message, application, component)
        
        conn = self._get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute('''
                        INSERT INTO agent_memory 
                        (agent_name, application, component, error_type, error_signature, 
                         context_data, decision_type, decision, reasoning, confidence, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    ''', (
                        self.agent_name,
                        application,
                        component,
                        error_type,
                        error_sig,
                        json.dumps(context_data or {}),
                        decision_type,
                        decision,
                        reasoning,
                        confidence,
                        json.dumps(metadata or {})
                    ))
                    return cur.fetchone()[0]
        finally:
            conn.close()
    
    def recall_similar_decisions(
        self,
        application: str,
        component: str,
        error_type: str,
        error_message: str,
        limit: int = 5,
        min_confidence: float = 0.3,
        days_back: int = 90
    ) -> List[Dict]:
        """
        Busca decisões similares anteriores.
        
        Args:
            application: Nome da aplicação
            component: Componente
            error_type: Tipo de erro
            error_message: Mensagem de erro
            limit: Número máximo de resultados
            min_confidence: Confiança mínima
            days_back: Quantos dias buscar no histórico
            
        Returns:
            Lista de decisões similares ordenadas por relevância
        """
        error_sig = self._generate_error_signature(error_type, error_message, application, component)
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Busca exata por signature primeiro
                cur.execute('''
                    SELECT 
                        id, created_at, application, component, error_type,
                        decision_type, decision, reasoning, confidence,
                        outcome, outcome_details, feedback_score,
                        context_data, metadata
                    FROM agent_memory
                    WHERE agent_name = %s
                      AND error_signature = %s
                      AND confidence >= %s
                      AND created_at >= %s
                    ORDER BY created_at DESC, confidence DESC
                    LIMIT %s
                ''', (self.agent_name, error_sig, min_confidence, cutoff_date, limit))
                
                exact_matches = cur.fetchall()
                
                # Se não houver matches exatos, busca por aplicação/componente
                if not exact_matches:
                    cur.execute('''
                        SELECT 
                            id, created_at, application, component, error_type,
                            decision_type, decision, reasoning, confidence,
                            outcome, outcome_details, feedback_score,
                            context_data, metadata
                        FROM agent_memory
                        WHERE agent_name = %s
                          AND application = %s
                          AND component = %s
                          AND error_type = %s
                          AND confidence >= %s
                          AND created_at >= %s
                        ORDER BY created_at DESC, confidence DESC
                        LIMIT %s
                    ''', (self.agent_name, application, component, error_type, 
                          min_confidence, cutoff_date, limit))
                    
                    return [dict(row) for row in cur.fetchall()]
                
                return [dict(row) for row in exact_matches]
        finally:
            conn.close()
    
    def update_decision_outcome(
        self,
        decision_id: int,
        outcome: str,
        outcome_details: Dict = None,
        feedback_score: float = None
    ):
        """
        Atualiza o resultado de uma decisão anterior.
        
        Args:
            decision_id: ID da decisão
            outcome: Resultado (success, failure, partial)
            outcome_details: Detalhes do resultado
            feedback_score: Score de feedback (-1.0 a 1.0)
        """
        conn = self._get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute('''
                        UPDATE agent_memory
                        SET outcome = %s,
                            outcome_details = %s,
                            feedback_score = %s
                        WHERE id = %s
                    ''', (outcome, json.dumps(outcome_details or {}), feedback_score, decision_id))
        finally:
            conn.close()
    
    def learn_pattern(
        self,
        pattern_type: str,
        pattern_data: Dict,
        success: bool = True
    ):
        """
        Aprende um padrão a partir de experiências.
        
        Args:
            pattern_type: Tipo de padrão (error_recovery, deployment_check, etc)
            pattern_data: Dados do padrão
            success: Se a aplicação do padrão foi bem-sucedida
        """
        pattern_sig = hashlib.sha256(
            f"{pattern_type}:{json.dumps(pattern_data, sort_keys=True)}".encode()
        ).hexdigest()[:16]
        
        conn = self._get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    # Tenta atualizar padrão existente
                    cur.execute('''
                        INSERT INTO agent_learned_patterns 
                        (agent_name, pattern_type, pattern_signature, pattern_data,
                         occurrences, success_count, failure_count, last_seen_at)
                        VALUES (%s, %s, %s, %s, 1, %s, %s, now())
                        ON CONFLICT (pattern_signature) DO UPDATE SET
                            occurrences = agent_learned_patterns.occurrences + 1,
                            success_count = agent_learned_patterns.success_count + %s,
                            failure_count = agent_learned_patterns.failure_count + %s,
                            confidence = CASE 
                                WHEN (agent_learned_patterns.success_count + %s + 
                                      agent_learned_patterns.failure_count + %s) > 0
                                THEN (agent_learned_patterns.success_count + %s)::float / 
                                     (agent_learned_patterns.success_count + %s + 
                                      agent_learned_patterns.failure_count + %s)
                                ELSE 0.5
                            END,
                            last_seen_at = now(),
                            updated_at = now()
                    ''', (
                        self.agent_name,
                        pattern_type,
                        pattern_sig,
                        json.dumps(pattern_data),
                        1 if success else 0,
                        0 if success else 1,
                        1 if success else 0,
                        0 if success else 1,
                        1 if success else 0,
                        0 if success else 1,
                        1 if success else 0,
                        1 if success else 0,
                        0 if success else 1
                    ))
        finally:
            conn.close()
    
    def get_learned_patterns(
        self,
        pattern_type: str = None,
        min_confidence: float = 0.6,
        min_occurrences: int = 2
    ) -> List[Dict]:
        """
        Recupera padrões aprendidos.
        
        Args:
            pattern_type: Filtrar por tipo de padrão
            min_confidence: Confiança mínima
            min_occurrences: Número mínimo de ocorrências
            
        Returns:
            Lista de padrões aprendidos
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if pattern_type:
                    cur.execute('''
                        SELECT *
                        FROM agent_learned_patterns
                        WHERE agent_name = %s
                          AND pattern_type = %s
                          AND confidence >= %s
                          AND occurrences >= %s
                        ORDER BY confidence DESC, occurrences DESC
                    ''', (self.agent_name, pattern_type, min_confidence, min_occurrences))
                else:
                    cur.execute('''
                        SELECT *
                        FROM agent_learned_patterns
                        WHERE agent_name = %s
                          AND confidence >= %s
                          AND occurrences >= %s
                        ORDER BY confidence DESC, occurrences DESC
                    ''', (self.agent_name, min_confidence, min_occurrences))
                
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()
    
    def get_decision_statistics(
        self,
        application: str = None,
        component: str = None,
        days_back: int = 30
    ) -> Dict:
        """
        Obtém estatísticas de decisões.
        
        Args:
            application: Filtrar por aplicação
            component: Filtrar por componente
            days_back: Período de análise
            
        Returns:
            Estatísticas agregadas
        """
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                where_clauses = ['agent_name = %s', 'created_at >= %s']
                params = [self.agent_name, cutoff_date]
                
                if application:
                    where_clauses.append('application = %s')
                    params.append(application)
                if component:
                    where_clauses.append('component = %s')
                    params.append(component)
                
                where_sql = ' AND '.join(where_clauses)
                
                cur.execute(f'''
                    SELECT 
                        COUNT(*) as total_decisions,
                        COUNT(DISTINCT application) as applications_count,
                        COUNT(DISTINCT component) as components_count,
                        COUNT(DISTINCT error_signature) as unique_errors,
                        AVG(confidence) as avg_confidence,
                        COUNT(CASE WHEN outcome = 'success' THEN 1 END) as successes,
                        COUNT(CASE WHEN outcome = 'failure' THEN 1 END) as failures,
                        AVG(feedback_score) as avg_feedback
                    FROM agent_memory
                    WHERE {where_sql}
                ''', params)
                
                stats = dict(cur.fetchone())
                
                # Busca decisões por tipo
                cur.execute(f'''
                    SELECT decision_type, COUNT(*) as count
                    FROM agent_memory
                    WHERE {where_sql}
                    GROUP BY decision_type
                ''', params)
                
                stats['decisions_by_type'] = {row['decision_type']: row['count'] 
                                             for row in cur.fetchall()}
                
                return stats
        finally:
            conn.close()


# Factory singleton para gerenciar instâncias de memória por agente
_memory_instances: Dict[str, AgentMemory] = {}

def get_agent_memory(agent_name: str, db_url: str = None) -> AgentMemory:
    """Obtém ou cria instância de memória para um agente"""
    if agent_name not in _memory_instances:
        _memory_instances[agent_name] = AgentMemory(agent_name, db_url)
    return _memory_instances[agent_name]
