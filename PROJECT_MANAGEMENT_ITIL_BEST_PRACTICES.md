# Melhores Práticas de Gestão de Projetos e Incidentes

Este documento contém conhecimentos fundamentais sobre gestão de projetos ágeis e gestão de incidentes (ITIL v4), destinados ao treinamento do agente coordenador.

## 1. Princípios Fundamentais da Gestão Ágil de Projetos
A gestão ágil foca na entrega contínua de valor através de ciclos iterativos.
*   **Indivíduos e Interações:** Pessoas e comunicação direta acima de processos rígidos.
*   **Software em Funcionamento:** O sucesso é medido pelo software funcional entregue ao usuário.
*   **Colaboração com o Cliente:** Proximidade constante com o cliente para ajustes finos de curso.
*   **Responder a Mudanças:** Flexibilidade para alterar o roadmap quando o mercado ou a tecnologia demandarem.

## 2. Papéis e Responsabilidades no Scrum
O Scrum organiza o time em três pilares principais:
*   **Product Owner (PO):** O "dono" do valor. Prioriza o *Product Backlog* e garante que o time trabalhe no que é mais importante para o negócio.
*   **Scrum Master (SM):** O facilitador. Remove impedimentos e garante que o time siga os ritos e valores do Scrum, agindo como um *Servant Leader*.
*   **Developers (Time de Desenvolvimento):** O time técnico. Autônomos e responsáveis pela entrega do incremento de software "Pronto" (Done) ao final de cada Sprint.

## 3. Kanban: Fluxo e Visibilidade
Diferente do Scrum, o Kanban foca na continuidade e otimização do fluxo:
*   **Visualização do Trabalho:** Uso do Quadro Kanban (Kanban Board) para tornar o trabalho invisível (código/tarefas) visível.
*   **Limitação do WIP (Work In Progress):** Limitar a quantidade de tarefas simultâneas para reduzir o multitarefa e acelerar o *Throughput*.
*   **Métricas de Fluxo:** Monitoramento de *Lead Time* (tempo total do pedido à entrega) e *Cycle Time* (tempo de execução técnica).

## 4. Ciclo de Vida de Gestão de Incidentes (ITIL v4)
Processo para restaurar serviços o mais rápido possível:
1.  **Detecção e Registro (Logging):** Identificação do erro e registro imediato no sistema de tickets.
2.  **Categorização e Priorização:** Classificação técnica e definição de prioridade baseada em **Impacto vs Urgência**.
3.  **Investigação e Diagnóstico:** Análise técnica para identificar o sintoma e possíveis soluções.
4.  **Resolução e Recuperação:** Aplicação de uma solução de contorno (*Workaround*) ou correção (fix) para restabelecer o serviço.
5.  **Encerramento (Closure):** Validação com o usuário e documentação na base de conhecimento (KEDB - Known Error Database).

## 5. Melhores Práticas para Coordenadores de Projetos de Software
*   **Gestão de Stakeholders:** Comunicação proativa de riscos e expectativas.
*   **Liderança Baseada em Métricas:** Decisões baseadas em dados (Burn-down, Velocity, Qualidade de Código).
*   **Mitigação de Riscos:** Identificação precoce de gargalos técnicos ou de pessoal.
*   **Documentação Primeiro:** Garantir que o conhecimento técnico seja indexável, evitando silos de informação.
*   **SLA (Service Level Agreement):** Monitorar e garantir o cumprimento de acordos de nível de serviço em incidentes.
