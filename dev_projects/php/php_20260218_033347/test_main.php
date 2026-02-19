<?php

use PHPUnit\Framework\TestCase;

class PhpAgentTest extends TestCase {
    public function testRegisterActivitySuccess() {
        // Configurações do Jira
        $jiraBaseUrl = 'https://your-jira-instance.atlassian.net';
        $jiraUsername = 'YOUR_JIRA_USERNAME';
        $jiraPassword = 'YOUR_JIRA_PASSWORD';

        // Criar o cliente Jira
        $jiraClient = new JiraClient($jiraBaseUrl, $jiraUsername, $jiraPassword);

        // Criar um agente PHP
        $phpAgent = new PhpAgent($jiraClient);

        // Criar uma atividade com valores válidos
        $activity = new Activity(1, 'This is a test activity');

        // Registrar a atividade
        $result = $phpAgent->registerActivity($activity);

        // Verifica se o resultado é um array
        $this->assertTrue(is_array($result));

        // Verifica se o campo 'id' está presente
        $this->assertArrayHasKey('id', $result);

        // Verifica se o campo 'key' está presente
        $this->assertArrayHasKey('key', $result);

        // Verifica se o campo 'summary' está presente
        $this->assertArrayHasKey('summary', $result);

        // Verifica se o campo 'description' está presente
        $this->assertArrayHasKey('description', $result);

        // Verifica se o campo 'status' está presente
        $this->assertArrayHasKey('status', $result);

        // Verifica se o campo 'priority' está presente
        $this->assertArrayHasKey('priority', $result);
    }

    public function testRegisterActivityFailure() {
        // Configurações do Jira
        $jiraBaseUrl = 'https://your-jira-instance.atlassian.net';
        $jiraUsername = 'YOUR_JIRA_USERNAME';
        $jiraPassword = 'YOUR_JIRA_PASSWORD';

        // Criar o cliente Jira
        $jiraClient = new JiraClient($jiraBaseUrl, $jiraUsername, $jiraPassword);

        // Criar um agente PHP
        $phpAgent = new PhpAgent($jiraClient);

        // Tenta registrar uma atividade com valores inválidos (por exemplo, status invalido)
        $activity = new Activity(1, 'This is a test activity', 'invalid_status');

        // Registrar a atividade
        try {
            $result = $phpAgent->registerActivity($activity);
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            // Verifica se o erro é do tipo JiraClientException
            $this->assertInstanceOf(JiraClientException::class, $e);

            // Verifica se a mensagem de erro contém a palavra "invalid_status"
            $this->assertStringContains('invalid_status', $e->getMessage());
        }
    }

    public function testRegisterActivityEdgeCase() {
        // Configurações do Jira
        $jiraBaseUrl = 'https://your-jira-instance.atlassian.net';
        $jiraUsername = 'YOUR_JIRA_USERNAME';
        $jiraPassword = 'YOUR_JIRA_PASSWORD';

        // Criar o cliente Jira
        $jiraClient = new JiraClient($jiraBaseUrl, $jiraUsername, $jiraPassword);

        // Criar um agente PHP
        $phpAgent = new PhpAgent($jiraClient);

        // Tenta registrar uma atividade com valores limite (por exemplo, status muito longo)
        $activity = new Activity(1, 'This is a test activity', str_repeat('a', 256));

        // Registrar a atividade
        try {
            $result = $phpAgent->registerActivity($activity);
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            // Verifica se o erro é do tipo JiraClientException
            $this->assertInstanceOf(JiraClientException::class, $e);

            // Verifica se a mensagem de erro contém a palavra "256"
            $this->assertStringContains('256', $e->getMessage());
        }
    }
}