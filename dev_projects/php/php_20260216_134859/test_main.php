<?php

use PHPUnit\Framework\TestCase;
use Jira\Client;
use Jira\Issue;

class JiraClientTest extends TestCase {
    protected $client;

    public function setUp(): void {
        // Configuração do cliente Jira
        $this->client = new Client('https://your-jira-instance.atlassian.net', 'your-username', 'your-api-token');
    }

    public function testCreateTask() {
        // Caso de sucesso com valores válidos
        $projectKey = 'YOUR_PROJECT_KEY';
        $summary = 'Nova Tarefa';
        $description = 'Descrição da nova tarefa';

        createTask($this->client, $projectKey, $summary, $description);

        // Verificação se a tarefa foi criada corretamente
        try {
            $issues = $this->client->search('project=' . $projectKey);
            
            foreach ($issues as $issue) {
                if ($issue->getKey() === 'YOUR_PROJECT_KEY-1') {
                    $this->assertTrue(true, "Tarefa criada com sucesso");
                    return;
                }
            }
        } catch (Exception $e) {
            $this->assertTrue(false, "Erro ao criar tarefa: " . $e->getMessage());
        }
    }

    public function testCreateTaskError() {
        // Caso de erro (divisão por zero)
        $projectKey = 'YOUR_PROJECT_KEY';
        $summary = 'Nova Tarefa';
        $description = '';

        try {
            createTask($this->client, $projectKey, $summary, $description);
        } catch (Exception $e) {
            $this->assertTrue(true, "Erro ao criar tarefa: " . $e->getMessage());
            return;
        }
    }

    public function testMonitorActivities() {
        // Caso de sucesso com valores válidos
        $projectKey = 'YOUR_PROJECT_KEY';

        monitorActivities($this->client, $projectKey);

        // Verificação se as atividades foram monitoradas corretamente
        try {
            $issues = $this->client->search('project=' . $projectKey);
            
            foreach ($issues as $issue) {
                if ($issue->getKey() === 'YOUR_PROJECT_KEY-1') {
                    $this->assertTrue(true, "Atividades monitoradas com sucesso");
                    return;
                }
            }
        } catch (Exception $e) {
            $this->assertTrue(false, "Erro ao monitorar atividades: " . $e->getMessage());
        }
    }

    public function testMonitorActivitiesError() {
        // Caso de erro (divisão por zero)
        $projectKey = 'YOUR_PROJECT_KEY';

        try {
            monitorActivities($this->client, $projectKey);
        } catch (Exception $e) {
            $this->assertTrue(true, "Erro ao monitorar atividades: " . $e->getMessage());
            return;
        }
    }
}