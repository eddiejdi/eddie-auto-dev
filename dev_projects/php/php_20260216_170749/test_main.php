<?php

use PHPUnit\Framework\TestCase;

class PHPAgentTest extends TestCase {
    public function testTrackActivitySuccess() {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.com';
        $username = 'your-username';
        $password = 'your-password';

        // Instanciar o PHPAgent
        $phpAgent = new PHPAgent($jiraUrl, $username, $password);

        // Exemplo de atividade a ser rastreada
        $issueKey = 'ABC-123';
        $activityType = 'Task Completed';
        $details = "The task was completed successfully.";

        // Rastrear a atividade
        $result = $phpAgent->trackActivity($issueKey, $activityType, $details);

        // Asserta que o resultado seja um string contendo "Activity tracked successfully"
        $this->assertStringContainsString("Activity tracked successfully", $result);
    }

    public function testTrackActivityError() {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.com';
        $username = 'your-username';
        $password = 'your-password';

        // Instanciar o PHPAgent
        $phpAgent = new PHPAgent($jiraUrl, $username, $password);

        // Exemplo de atividade a ser rastreada com um erro (divisão por zero)
        $issueKey = 'ABC-123';
        $activityType = 'Task Completed';
        $details = "The task was completed successfully.";

        try {
            // Rastrear a atividade
            $result = $phpAgent->trackActivity($issueKey, $activityType, $details);
        } catch (\Exception $e) {
            // Asserta que o erro seja um string contendo "Error tracking activity"
            $this->assertStringContainsString("Error tracking activity", $e->getMessage());
        }
    }

    public function testTrackActivityEdgeCase() {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.com';
        $username = 'your-username';
        $password = 'your-password';

        // Instanciar o PHPAgent
        $phpAgent = new PHPAgent($jiraUrl, $username, $password);

        // Exemplo de atividade a ser rastreada com um edge case (string vazia)
        $issueKey = 'ABC-123';
        $activityType = '';
        $details = "The task was completed successfully.";

        try {
            // Rastrear a atividade
            $result = $phpAgent->trackActivity($issueKey, $activityType, $details);
        } catch (\Exception $e) {
            // Asserta que o erro seja um string contendo "Error tracking activity"
            $this->assertStringContainsString("Error tracking activity", $e->getMessage());
        }
    }
}