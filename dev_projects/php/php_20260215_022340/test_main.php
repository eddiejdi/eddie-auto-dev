<?php

use PhpAgent\Agent;
use PhpAgent\Exception\AgentException;

class JiraIntegrationTest extends \PHPUnit\Framework\TestCase {
    private $jiraUrl = 'https://your-jira-instance.atlassian.net';
    private $username = 'your-username';
    private $password;

    public function setUp() {
        $this->jiraUrl = 'https://your-jira-instance.atlassian.net';
        $this->username = 'your-username';
        $this->password = 'your-password';
        $this->agent = new Agent();
    }

    public function testTrackActivitySuccess() {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Instancia da classe JiraIntegration
        $integration = new JiraIntegration($jiraUrl, $username, $password);

        // Exemplo de uso: Tracar uma atividade em um issue com valores válidos
        $issueKey = 'ABC-123';
        $activityDescription = 'This is a test activity.';
        $integration->trackActivity($issueKey, $activityDescription);

        // Verifica se o método foi chamado corretamente
        $this->assertTrue($integration->agent->isAuthenticated());
    }

    public function testTrackActivityError() {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Instancia da classe JiraIntegration
        $integration = new JiraIntegration($jiraUrl, $username, $password);

        // Exemplo de uso: Tracar uma atividade em um issue com valores inválidos
        $issueKey = 'ABC-123';
        $activityDescription = '';
        try {
            $integration->trackActivity($issueKey, $activityDescription);
            $this->fail('Expected an exception to be thrown');
        } catch (AgentException $e) {
            // Verifica se o erro é do tipo esperado
            $this->assertEquals('Invalid issue key', $e->getMessage());
        }
    }

    public function testTrackActivityEdgeCase() {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Instancia da classe JiraIntegration
        $integration = new JiraIntegration($jiraUrl, $username, $password);

        // Exemplo de uso: Tracar uma atividade em um issue com valores limite
        $issueKey = 'ABC-123';
        $activityDescription = str_repeat('a', 5000); // Tamanho máximo permitido para a descrição
        try {
            $integration->trackActivity($issueKey, $activityDescription);
            $this->fail('Expected an exception to be thrown');
        } catch (AgentException $e) {
            // Verifica se o erro é do tipo esperado
            $this->assertEquals('Invalid issue key', $e->getMessage());
        }
    }

    public function tearDown() {
        // Limpa as configurações após os testes
        unset($this->jiraUrl);
        unset($this->username);
        unset($this->password);
        unset($this->agent);
    }
}