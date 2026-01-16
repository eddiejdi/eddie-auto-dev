"""
Agente Especializado em BPM e Desenhos Técnicos

Especialidades:
- Business Process Management (BPM/BPMN 2.0)
- Desenhos técnicos e diagramas
- Draw.io (diagrams.net) - geração de arquivos .drawio
- Fluxogramas, diagramas de arquitetura, swimlanes
- Documentação visual de processos
"""
import os
import json
import uuid
import base64
import zlib
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

# Diretório para salvar diagramas
DIAGRAMS_DIR = Path(__file__).parent / "diagrams"
DIAGRAMS_DIR.mkdir(exist_ok=True)


@dataclass
class BPMNElement:
    """Elemento BPMN básico"""
    id: str
    name: str
    type: str  # task, gateway, event, subprocess, pool, lane
    x: int = 0
    y: int = 0
    width: int = 120
    height: int = 80
    style: str = ""
    connections: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BPMNProcess:
    """Processo BPMN completo"""
    id: str
    name: str
    elements: List[BPMNElement] = field(default_factory=list)
    flows: List[Dict[str, str]] = field(default_factory=list)
    pools: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class DrawIOGenerator:
    """Gerador de arquivos Draw.io (.drawio)"""
    
    # Estilos padrão para elementos BPMN
    STYLES = {
        "start_event": "ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#d5e8d4;strokeColor=#82b366;",
        "end_event": "ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#f8cecc;strokeColor=#b85450;strokeWidth=3;",
        "task": "rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;",
        "user_task": "rounded=1;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;",
        "service_task": "rounded=1;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;",
        "script_task": "rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;",
        "gateway_exclusive": "rhombus;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;",
        "gateway_parallel": "rhombus;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;",
        "gateway_inclusive": "rhombus;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;",
        "subprocess": "rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;strokeWidth=2;",
        "pool": "swimlane;horizontal=1;fillColor=#d5e8d4;strokeColor=#82b366;",
        "lane": "swimlane;horizontal=1;fillColor=none;strokeColor=#82b366;",
        "flow": "endArrow=classic;html=1;rounded=0;",
        "message_flow": "endArrow=classic;html=1;rounded=0;dashed=1;",
        "annotation": "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;",
        "data_object": "shape=note;whiteSpace=wrap;html=1;size=14;fillColor=#fff2cc;strokeColor=#d6b656;",
        "database": "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;size=15;fillColor=#dae8fc;strokeColor=#6c8ebf;",
        # Arquitetura
        "server": "rounded=0;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;",
        "cloud": "ellipse;shape=cloud;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;",
        "container": "rounded=1;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;dashed=1;",
        "api": "rounded=1;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;",
        "microservice": "rounded=1;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;",
    }
    
    def __init__(self):
        self.cell_id = 0
    
    def _next_id(self) -> str:
        self.cell_id += 1
        return str(self.cell_id)
    
    def create_empty_diagram(self, name: str = "Untitled Diagram") -> ET.Element:
        """Cria estrutura base de um arquivo .drawio"""
        mxfile = ET.Element("mxfile", {
            "host": "eddie-auto-dev",
            "modified": datetime.now().isoformat(),
            "agent": "BPMAgent/1.0",
            "version": "21.0.0",
            "type": "device"
        })
        
        diagram = ET.SubElement(mxfile, "diagram", {
            "id": str(uuid.uuid4())[:8],
            "name": name
        })
        
        mxGraphModel = ET.SubElement(diagram, "mxGraphModel", {
            "dx": "1422",
            "dy": "794",
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": "1169",
            "pageHeight": "827",
            "math": "0",
            "shadow": "0"
        })
        
        root = ET.SubElement(mxGraphModel, "root")
        ET.SubElement(root, "mxCell", {"id": "0"})
        ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
        
        return mxfile
    
    def add_element(self, root: ET.Element, element: BPMNElement) -> str:
        """Adiciona um elemento ao diagrama"""
        cell_id = self._next_id()
        
        style = element.style or self.STYLES.get(element.type, self.STYLES["task"])
        
        cell = ET.SubElement(root, "mxCell", {
            "id": cell_id,
            "value": element.name,
            "style": style,
            "vertex": "1",
            "parent": "1"
        })
        
        ET.SubElement(cell, "mxGeometry", {
            "x": str(element.x),
            "y": str(element.y),
            "width": str(element.width),
            "height": str(element.height),
            "as": "geometry"
        })
        
        return cell_id
    
    def add_connection(self, root: ET.Element, source_id: str, target_id: str, 
                       label: str = "", style: str = None) -> str:
        """Adiciona uma conexão entre elementos"""
        cell_id = self._next_id()
        
        conn_style = style or self.STYLES["flow"]
        
        cell = ET.SubElement(root, "mxCell", {
            "id": cell_id,
            "value": label,
            "style": conn_style,
            "edge": "1",
            "parent": "1",
            "source": source_id,
            "target": target_id
        })
        
        geometry = ET.SubElement(cell, "mxGeometry", {
            "relative": "1",
            "as": "geometry"
        })
        
        return cell_id
    
    def to_xml_string(self, mxfile: ET.Element) -> str:
        """Converte para string XML"""
        return ET.tostring(mxfile, encoding="unicode", method="xml")
    
    def save(self, mxfile: ET.Element, filepath: str) -> str:
        """Salva o diagrama em arquivo .drawio"""
        xml_str = self.to_xml_string(mxfile)
        
        # Garantir extensão .drawio
        if not filepath.endswith('.drawio'):
            filepath += '.drawio'
        
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(xml_str)
        
        logger.info(f"Diagrama salvo em: {path}")
        return str(path)


class BPMAgent:
    """
    Agente especializado em BPM e desenhos técnicos.
    
    Capabilities:
    - Criar diagramas BPMN 2.0
    - Gerar arquivos .drawio
    - Desenhar fluxogramas
    - Criar diagramas de arquitetura
    - Documentar processos de negócio
    """
    
    def __init__(self, llm_client=None):
        self.generator = DrawIOGenerator()
        self.llm = llm_client
        self.processes: Dict[str, BPMNProcess] = {}
        
        # Templates de processos comuns
        self.templates = {
            "approval_flow": self._template_approval_flow,
            "order_process": self._template_order_process,
            "ci_cd_pipeline": self._template_cicd_pipeline,
            "microservices": self._template_microservices,
            "user_registration": self._template_user_registration,
        }
    
    def create_process(self, name: str, description: str = "") -> BPMNProcess:
        """Cria um novo processo BPMN"""
        process_id = f"proc_{uuid.uuid4().hex[:8]}"
        process = BPMNProcess(id=process_id, name=name)
        self.processes[process_id] = process
        logger.info(f"Processo criado: {name} ({process_id})")
        return process
    
    def add_element_to_process(self, process_id: str, element_type: str, 
                                name: str, **kwargs) -> BPMNElement:
        """Adiciona elemento a um processo"""
        if process_id not in self.processes:
            raise ValueError(f"Processo não encontrado: {process_id}")
        
        element = BPMNElement(
            id=f"elem_{uuid.uuid4().hex[:8]}",
            name=name,
            type=element_type,
            **kwargs
        )
        
        self.processes[process_id].elements.append(element)
        return element
    
    def add_flow(self, process_id: str, source_id: str, target_id: str, 
                 label: str = "") -> Dict[str, str]:
        """Adiciona fluxo entre elementos"""
        if process_id not in self.processes:
            raise ValueError(f"Processo não encontrado: {process_id}")
        
        flow = {
            "id": f"flow_{uuid.uuid4().hex[:8]}",
            "source": source_id,
            "target": target_id,
            "label": label
        }
        
        self.processes[process_id].flows.append(flow)
        return flow
    
    def generate_drawio(self, process_id: str, output_path: str = None) -> str:
        """Gera arquivo .drawio a partir de um processo"""
        if process_id not in self.processes:
            raise ValueError(f"Processo não encontrado: {process_id}")
        
        process = self.processes[process_id]
        mxfile = self.generator.create_empty_diagram(process.name)
        
        # Encontra o root element
        root = mxfile.find(".//root")
        
        # Mapeia IDs para células
        id_map = {}
        
        # Adiciona elementos
        for elem in process.elements:
            cell_id = self.generator.add_element(root, elem)
            id_map[elem.id] = cell_id
        
        # Adiciona fluxos
        for flow in process.flows:
            source_cell = id_map.get(flow["source"], flow["source"])
            target_cell = id_map.get(flow["target"], flow["target"])
            self.generator.add_connection(root, source_cell, target_cell, flow.get("label", ""))
        
        # Define caminho de saída
        if not output_path:
            output_path = str(DIAGRAMS_DIR / f"{process.name.replace(' ', '_')}.drawio")
        
        return self.generator.save(mxfile, output_path)
    
    def create_from_template(self, template_name: str, 
                             custom_name: str = None, **kwargs) -> str:
        """Cria diagrama a partir de template"""
        if template_name not in self.templates:
            available = ", ".join(self.templates.keys())
            raise ValueError(f"Template não encontrado: {template_name}. Disponíveis: {available}")
        
        return self.templates[template_name](custom_name, **kwargs)
    
    def _template_approval_flow(self, name: str = None, **kwargs) -> str:
        """Template: Fluxo de Aprovação"""
        process = self.create_process(name or "Fluxo de Aprovação")
        
        # Elementos
        start = self.add_element_to_process(process.id, "start_event", "Início", x=50, y=200, width=40, height=40)
        submit = self.add_element_to_process(process.id, "user_task", "Submeter\nSolicitação", x=150, y=180)
        review = self.add_element_to_process(process.id, "user_task", "Revisar\nSolicitação", x=320, y=180)
        gateway = self.add_element_to_process(process.id, "gateway_exclusive", "Aprovado?", x=490, y=190, width=50, height=50)
        approve = self.add_element_to_process(process.id, "service_task", "Processar\nAprovação", x=600, y=100)
        reject = self.add_element_to_process(process.id, "service_task", "Notificar\nRejeição", x=600, y=260)
        end_ok = self.add_element_to_process(process.id, "end_event", "Fim\n(Aprovado)", x=770, y=110, width=40, height=40)
        end_no = self.add_element_to_process(process.id, "end_event", "Fim\n(Rejeitado)", x=770, y=270, width=40, height=40)
        
        # Fluxos
        self.add_flow(process.id, start.id, submit.id)
        self.add_flow(process.id, submit.id, review.id)
        self.add_flow(process.id, review.id, gateway.id)
        self.add_flow(process.id, gateway.id, approve.id, "Sim")
        self.add_flow(process.id, gateway.id, reject.id, "Não")
        self.add_flow(process.id, approve.id, end_ok.id)
        self.add_flow(process.id, reject.id, end_no.id)
        
        return self.generate_drawio(process.id)
    
    def _template_order_process(self, name: str = None, **kwargs) -> str:
        """Template: Processo de Pedido"""
        process = self.create_process(name or "Processo de Pedido")
        
        start = self.add_element_to_process(process.id, "start_event", "Pedido\nRecebido", x=50, y=200, width=40, height=40)
        validate = self.add_element_to_process(process.id, "service_task", "Validar\nPedido", x=150, y=180)
        check_stock = self.add_element_to_process(process.id, "service_task", "Verificar\nEstoque", x=320, y=180)
        gw_stock = self.add_element_to_process(process.id, "gateway_exclusive", "Em\nEstoque?", x=490, y=190, width=50, height=50)
        reserve = self.add_element_to_process(process.id, "service_task", "Reservar\nProdutos", x=600, y=100)
        backorder = self.add_element_to_process(process.id, "service_task", "Criar\nBackorder", x=600, y=260)
        payment = self.add_element_to_process(process.id, "service_task", "Processar\nPagamento", x=770, y=180)
        ship = self.add_element_to_process(process.id, "service_task", "Enviar\nPedido", x=940, y=180)
        end = self.add_element_to_process(process.id, "end_event", "Fim", x=1110, y=190, width=40, height=40)
        
        self.add_flow(process.id, start.id, validate.id)
        self.add_flow(process.id, validate.id, check_stock.id)
        self.add_flow(process.id, check_stock.id, gw_stock.id)
        self.add_flow(process.id, gw_stock.id, reserve.id, "Sim")
        self.add_flow(process.id, gw_stock.id, backorder.id, "Não")
        self.add_flow(process.id, reserve.id, payment.id)
        self.add_flow(process.id, backorder.id, payment.id)
        self.add_flow(process.id, payment.id, ship.id)
        self.add_flow(process.id, ship.id, end.id)
        
        return self.generate_drawio(process.id)
    
    def _template_cicd_pipeline(self, name: str = None, **kwargs) -> str:
        """Template: Pipeline CI/CD"""
        process = self.create_process(name or "Pipeline CI/CD")
        
        # Elementos do pipeline
        start = self.add_element_to_process(process.id, "start_event", "Push/PR", x=50, y=200, width=40, height=40)
        checkout = self.add_element_to_process(process.id, "script_task", "Checkout\nCódigo", x=150, y=180)
        install = self.add_element_to_process(process.id, "script_task", "Instalar\nDependências", x=320, y=180)
        lint = self.add_element_to_process(process.id, "script_task", "Lint &\nFormat", x=490, y=180)
        test = self.add_element_to_process(process.id, "script_task", "Executar\nTestes", x=660, y=180)
        gw_test = self.add_element_to_process(process.id, "gateway_exclusive", "Testes\nOK?", x=830, y=190, width=50, height=50)
        build = self.add_element_to_process(process.id, "script_task", "Build\nArtifact", x=940, y=100)
        fail = self.add_element_to_process(process.id, "service_task", "Notificar\nFalha", x=940, y=260)
        deploy_stg = self.add_element_to_process(process.id, "service_task", "Deploy\nStaging", x=1110, y=100)
        deploy_prod = self.add_element_to_process(process.id, "service_task", "Deploy\nProd", x=1280, y=100)
        end_ok = self.add_element_to_process(process.id, "end_event", "✓", x=1450, y=110, width=40, height=40)
        end_fail = self.add_element_to_process(process.id, "end_event", "✗", x=1110, y=270, width=40, height=40)
        
        self.add_flow(process.id, start.id, checkout.id)
        self.add_flow(process.id, checkout.id, install.id)
        self.add_flow(process.id, install.id, lint.id)
        self.add_flow(process.id, lint.id, test.id)
        self.add_flow(process.id, test.id, gw_test.id)
        self.add_flow(process.id, gw_test.id, build.id, "Sim")
        self.add_flow(process.id, gw_test.id, fail.id, "Não")
        self.add_flow(process.id, build.id, deploy_stg.id)
        self.add_flow(process.id, deploy_stg.id, deploy_prod.id)
        self.add_flow(process.id, deploy_prod.id, end_ok.id)
        self.add_flow(process.id, fail.id, end_fail.id)
        
        return self.generate_drawio(process.id)
    
    def _template_microservices(self, name: str = None, **kwargs) -> str:
        """Template: Arquitetura de Microserviços"""
        process = self.create_process(name or "Arquitetura Microserviços")
        
        # Cliente e Gateway
        client = self.add_element_to_process(process.id, "cloud", "Cliente\n(Browser/App)", x=50, y=200, width=100, height=60)
        gateway = self.add_element_to_process(process.id, "api", "API Gateway", x=220, y=200, width=100, height=60)
        
        # Microserviços
        auth = self.add_element_to_process(process.id, "microservice", "Auth\nService", x=400, y=50, width=100, height=60)
        user = self.add_element_to_process(process.id, "microservice", "User\nService", x=400, y=150, width=100, height=60)
        order = self.add_element_to_process(process.id, "microservice", "Order\nService", x=400, y=250, width=100, height=60)
        payment = self.add_element_to_process(process.id, "microservice", "Payment\nService", x=400, y=350, width=100, height=60)
        
        # Message Broker
        broker = self.add_element_to_process(process.id, "container", "Message Broker\n(RabbitMQ/Kafka)", x=580, y=180, width=120, height=80)
        
        # Databases
        db_user = self.add_element_to_process(process.id, "database", "User DB", x=750, y=100, width=60, height=60)
        db_order = self.add_element_to_process(process.id, "database", "Order DB", x=750, y=200, width=60, height=60)
        db_payment = self.add_element_to_process(process.id, "database", "Payment DB", x=750, y=300, width=60, height=60)
        
        # Conexões
        self.add_flow(process.id, client.id, gateway.id)
        self.add_flow(process.id, gateway.id, auth.id)
        self.add_flow(process.id, gateway.id, user.id)
        self.add_flow(process.id, gateway.id, order.id)
        self.add_flow(process.id, gateway.id, payment.id)
        self.add_flow(process.id, user.id, broker.id)
        self.add_flow(process.id, order.id, broker.id)
        self.add_flow(process.id, payment.id, broker.id)
        self.add_flow(process.id, user.id, db_user.id)
        self.add_flow(process.id, order.id, db_order.id)
        self.add_flow(process.id, payment.id, db_payment.id)
        
        return self.generate_drawio(process.id)
    
    def _template_user_registration(self, name: str = None, **kwargs) -> str:
        """Template: Fluxo de Cadastro de Usuário"""
        process = self.create_process(name or "Cadastro de Usuário")
        
        start = self.add_element_to_process(process.id, "start_event", "Início", x=50, y=200, width=40, height=40)
        form = self.add_element_to_process(process.id, "user_task", "Preencher\nFormulário", x=150, y=180)
        validate = self.add_element_to_process(process.id, "service_task", "Validar\nDados", x=320, y=180)
        gw_valid = self.add_element_to_process(process.id, "gateway_exclusive", "Válido?", x=490, y=190, width=50, height=50)
        create = self.add_element_to_process(process.id, "service_task", "Criar\nUsuário", x=600, y=100)
        error = self.add_element_to_process(process.id, "service_task", "Mostrar\nErros", x=600, y=280)
        send_email = self.add_element_to_process(process.id, "service_task", "Enviar Email\nConfirmação", x=770, y=100)
        confirm = self.add_element_to_process(process.id, "user_task", "Confirmar\nEmail", x=940, y=100)
        activate = self.add_element_to_process(process.id, "service_task", "Ativar\nConta", x=1110, y=100)
        end = self.add_element_to_process(process.id, "end_event", "Fim", x=1280, y=110, width=40, height=40)
        
        self.add_flow(process.id, start.id, form.id)
        self.add_flow(process.id, form.id, validate.id)
        self.add_flow(process.id, validate.id, gw_valid.id)
        self.add_flow(process.id, gw_valid.id, create.id, "Sim")
        self.add_flow(process.id, gw_valid.id, error.id, "Não")
        self.add_flow(process.id, error.id, form.id, "Corrigir")
        self.add_flow(process.id, create.id, send_email.id)
        self.add_flow(process.id, send_email.id, confirm.id)
        self.add_flow(process.id, confirm.id, activate.id)
        self.add_flow(process.id, activate.id, end.id)
        
        return self.generate_drawio(process.id)
    
    def create_custom_diagram(self, elements: List[Dict], flows: List[Dict], 
                               name: str = "Custom Diagram") -> str:
        """
        Cria diagrama customizado a partir de especificação.
        
        elements: Lista de dicts com {name, type, x, y, width?, height?}
        flows: Lista de dicts com {source, target, label?}
        """
        process = self.create_process(name)
        
        elem_map = {}
        for elem_spec in elements:
            elem = self.add_element_to_process(
                process.id,
                elem_spec.get("type", "task"),
                elem_spec.get("name", ""),
                x=elem_spec.get("x", 0),
                y=elem_spec.get("y", 0),
                width=elem_spec.get("width", 120),
                height=elem_spec.get("height", 80)
            )
            elem_map[elem_spec.get("name", elem.id)] = elem.id
        
        for flow_spec in flows:
            source = elem_map.get(flow_spec.get("source"), flow_spec.get("source"))
            target = elem_map.get(flow_spec.get("target"), flow_spec.get("target"))
            self.add_flow(process.id, source, target, flow_spec.get("label", ""))
        
        return self.generate_drawio(process.id)
    
    def list_templates(self) -> List[str]:
        """Lista templates disponíveis"""
        return list(self.templates.keys())
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Retorna capabilities do agente"""
        return {
            "name": "BPM Agent",
            "version": "1.0.0",
            "specialties": [
                "Business Process Management (BPM)",
                "BPMN 2.0 Diagrams",
                "Draw.io file generation",
                "Flowcharts",
                "Architecture diagrams",
                "Swimlane diagrams",
                "Technical documentation"
            ],
            "templates": self.list_templates(),
            "output_formats": [".drawio", ".xml"],
            "element_types": list(DrawIOGenerator.STYLES.keys())
        }


# Instância global do agente
_bpm_agent_instance = None

def get_bpm_agent() -> BPMAgent:
    """Retorna instância singleton do BPM Agent"""
    global _bpm_agent_instance
    if _bpm_agent_instance is None:
        _bpm_agent_instance = BPMAgent()
    return _bpm_agent_instance


# CLI para uso direto
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="BPM Agent - Gerador de Diagramas")
    parser.add_argument("--template", "-t", help="Nome do template a usar")
    parser.add_argument("--list", "-l", action="store_true", help="Listar templates")
    parser.add_argument("--output", "-o", help="Caminho de saída")
    parser.add_argument("--name", "-n", help="Nome do diagrama")
    parser.add_argument("--smoke", action="store_true", help="Smoke test para CI")
    
    args = parser.parse_args()
    
    agent = get_bpm_agent()
    
    if args.smoke:
        print("🔥 BPM Agent Smoke Test...")
        print(f"   ✅ Templates: {len(agent.list_templates())}")
        print(f"   ✅ Capabilities: {agent.get_capabilities()['name']}")
        print(f"   ✅ Element types: {len(DrawIOGenerator.STYLES)}")
        print("🎉 Smoke test passed!")
        exit(0)
    
    if args.list:
        print("📋 Templates disponíveis:")
        for t in agent.list_templates():
            print(f"   • {t}")
        exit(0)
    
    if args.template:
        output = agent.create_from_template(
            args.template, 
            custom_name=args.name
        )
        print(f"✅ Diagrama gerado: {output}")
    else:
        # Gera exemplo padrão
        output = agent.create_from_template("ci_cd_pipeline")
        print(f"✅ Exemplo gerado: {output}")
