#!/usr/bin/env python3
"""Script para atualizar agent_manager.py com integracao do RequirementsAnalyst"""
import re

# Ler arquivo
with open('/home/home-lab/myClaude/specialized_agents/agent_manager.py', 'r') as f:
    content = f.read()

# Codigo a inserir antes do singleton
new_methods = '''
    # ==========================================
    # INTEGRACAO COM ANALISTA DE REQUISITOS
    # ==========================================

    async def analyze_project_requirements(self, description: str) -> Dict[str, Any]:
        """Analisa requisitos de um projeto"""
        requirement = await self.requirements_analyst.analyze_requirements(description)
        return {
            "success": True,
            "requirement": requirement.to_dict()
        }

    async def generate_requirement_docs(self, req_id: str, doc_type: str = "full") -> Dict[str, Any]:
        """Gera documentacao para um requisito"""
        try:
            docs = await self.requirements_analyst.generate_documentation(req_id, doc_type)
            return {"success": True, "documentation": docs}
        except ValueError as e:
            return {"success": False, "error": str(e)}

    async def generate_requirement_tests(self, req_id: str, language: str = "python") -> Dict[str, Any]:
        """Gera casos de teste para um requisito"""
        try:
            test_cases = await self.requirements_analyst.generate_test_cases(req_id, language)
            test_code = await self.requirements_analyst.generate_test_code(req_id, language)
            return {
                "success": True,
                "test_cases": test_cases,
                "test_code": test_code
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}

    async def create_project_with_requirements(
        self,
        description: str,
        language: str,
        project_name: str = None
    ) -> Dict[str, Any]:
        """Fluxo completo: analisa requisitos -> gera docs -> cria projeto -> valida entrega"""
        requirement = await self.requirements_analyst.analyze_requirements(description)
        await self.requirements_analyst.generate_documentation(requirement.id, "technical")
        task_package = await self.requirements_analyst.prepare_task_for_programmer(
            requirement.id, language
        )
        agent = self.get_or_create_agent(language)
        task = agent.create_task(task_package["task_description"], {
            "requirement_id": requirement.id,
            "project_name": project_name
        })
        result_task = await agent.execute_task(task.id)
        validation = await self.requirements_analyst.validate_agent_output(
            requirement.id, result_task, agent
        )
        return {
            "success": result_task.status.value == "completed" and validation["approved"],
            "requirement": requirement.to_dict(),
            "task": result_task.to_dict(),
            "validation": validation,
            "documentation": task_package["documentation"],
            "test_code": task_package["test_code"]
        }

    async def review_agent_delivery(
        self,
        task_id: str,
        requirement_id: str,
        agent_name: str,
        code: str,
        tests: str = ""
    ) -> Dict[str, Any]:
        """Revisa entrega de um agente"""
        review = await self.requirements_analyst.review_delivery(
            task_id, requirement_id, agent_name, code, tests
        )
        return {
            "success": True,
            "review": review.to_dict()
        }

    def get_requirements_status(self) -> Dict[str, Any]:
        """Status do analista de requisitos"""
        return self.requirements_analyst.get_status()

    def list_all_requirements(self) -> List[Dict]:
        """Lista todos os requisitos"""
        return self.requirements_analyst.list_requirements()

    def list_all_reviews(self) -> List[Dict]:
        """Lista todas as reviews"""
        return self.requirements_analyst.list_reviews()


'''

# Verificar se ja foi adicionado
if 'analyze_project_requirements' not in content:
    # Encontrar onde inserir (antes do singleton)
    pattern = r'\n# Singleton global'
    replacement = new_methods + '\n# Singleton global'
    content = re.sub(pattern, replacement, content)
    
    # Salvar
    with open('/home/home-lab/myClaude/specialized_agents/agent_manager.py', 'w') as f:
        f.write(content)
    
    print("agent_manager.py atualizado com sucesso!")
else:
    print("Metodos ja existem no arquivo.")
