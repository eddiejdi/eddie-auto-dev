<?php

use PHPUnit\Framework\TestCase;

class Scrum15JiraIntegrationTest extends TestCase {
    private $integration;

    public function setUp() {
        // Inicializar o cliente do Jira
        $this->jiraClient = new JiraClient([
            'url' => 'https://your-jira-instance.atlassian.net',
            'auth' => ['your-username', 'your-password']
        ]);

        // Selecionar uma tarefa específica (exemplo: ID 123)
        $this->issueId = 123;
    }

    public function testMonitorarAtividadesComSucesso() {
        try {
            // Criar uma tarefa fictícia
            $issueData = [
                'fields' => [
                    'project' => ['key' => 'SCRUM'],
                    'summary' => 'Teste de monitoramento',
                    'description' => 'Descrição da tarefa',
                    'status' => ['name' => 'To Do']
                ]
            ];

            $this->jiraClient->createIssue($issueData);

            // Monitorar atividades
            $this->integration = new Scrum15JiraIntegration('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
            $this->integration->monitorarAtividades();

            // Verificar se a tarefa foi atualizada corretamente
            $updatedIssue = $this->jiraClient->getIssue($this->issueId);
            $this->assertEquals('In Progress', $updatedIssue->getStatus()->getName());
        } catch (\Exception $e) {
            $this->fail("Erro ao monitorar atividades: " . $e->getMessage());
        }
    }

    public function testMonitorarAtividadesComFalha() {
        try {
            // Criar uma tarefa fictícia com um status inválido
            $issueData = [
                'fields' => [
                    'project' => ['key' => 'SCRUM'],
                    'summary' => 'Teste de monitoramento',
                    'description' => 'Descrição da tarefa',
                    'status' => ['name' => 'In Progress']
                ]
            ];

            $this->jiraClient->createIssue($issueData);

            // Monitorar atividades
            $this->integration = new Scrum15JiraIntegration('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
            $this->integration->monitorarAtividades();

            // Verificar se a tarefa foi atualizada corretamente
            $updatedIssue = $this->jiraClient->getIssue($this->issueId);
            $this->assertEquals('In Progress', $updatedIssue->getStatus()->getName());
        } catch (\Exception $e) {
            $this->fail("Erro ao monitorar atividades: " . $e->getMessage());
        }
    }

    public function testMonitorarAtividadesComEdgeCase() {
        try {
            // Criar uma tarefa fictícia com um status inválido
            $issueData = [
                'fields' => [
                    'project' => ['key' => 'SCRUM'],
                    'summary' => 'Teste de monitoramento',
                    'description' => 'Descrição da tarefa',
                    'status' => ['name' => 'In Progress']
                ]
            ];

            $this->jiraClient->createIssue($issueData);

            // Monitorar atividades
            $this->integration = new Scrum15JiraIntegration('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
            $this->integration->monitorarAtividades();

            // Verificar se a tarefa foi atualizada corretamente
            $updatedIssue = $this->jiraClient->getIssue($this->issueId);
            $this->assertEquals('In Progress', $updatedIssue->getStatus()->getName());
        } catch (\Exception $e) {
            $this->fail("Erro ao monitorar atividades: " . $e->getMessage());
        }
    }
}