<?php

use PHPUnit\Framework\TestCase;
use Jira\Client;

class PHPAgentTest extends TestCase {
    private $phpAgent;

    protected function setUp(): void {
        // Configurar o cliente do Jira
        $url = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Criar uma instância do PHPAgent
        $this->phpAgent = new PHPAgent($url, $username, $password);
    }

    public function testTrackActivitySuccess() {
        // Caso de sucesso com valores válidos
        $issueKey = 'ABC-123';
        $activityDescription = "User logged in from IP address 192.168.1.1";

        try {
            // Registrar a atividade no Jira
            $this->phpAgent->trackActivity($issueKey, $activityDescription);

            // Verificar se o método criou um novo issue e adicionou-o ao Jira
            $issue = $this->phpAgent->jiraClient->issues()->get($issueKey);
            $this->assertNotEmpty($issue);
        } catch (\Exception $e) {
            $this->fail("Error tracking activity: " . $e->getMessage());
        }
    }

    public function testTrackActivityFailure() {
        // Caso de erro (divisão por zero)
        $issueKey = 'ABC-123';
        $activityDescription = "User logged in from IP address 0.0.0.0";

        try {
            // Registrar a atividade no Jira
            $this->phpAgent->trackActivity($issueKey, $activityDescription);
        } catch (\Exception $e) {
            // Verificar se o método lançou uma exceção de divisão por zero
            $this->assertEquals("Division by zero", $e->getMessage());
        }
    }

    public function testTrackActivityInvalidInput() {
        // Caso de erro (valores inválidos)
        $issueKey = 'ABC-123';
        $activityDescription = "";

        try {
            // Registrar a atividade no Jira
            $this->phpAgent->trackActivity($issueKey, $activityDescription);
        } catch (\Exception $e) {
            // Verificar se o método lançou uma exceção de valor inválido
            $this->assertEquals("Invalid input", $e->getMessage());
        }
    }

    public function testTrackActivityEdgeCase() {
        // Caso de edge case (valores limite)
        $issueKey = 'ABC-123';
        $activityDescription = "User logged in from IP address 999.999.999.999";

        try {
            // Registrar a atividade no Jira
            $this->phpAgent->trackActivity($issueKey, $activityDescription);
        } catch (\Exception $e) {
            // Verificar se o método lançou uma exceção de valor inválido
            $this->assertEquals("Invalid input", $e->getMessage());
        }
    }
}