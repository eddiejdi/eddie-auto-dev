<?php

use PHPUnit\Framework\TestCase;

class JiraLoggerTest extends TestCase {
    public function testLogMessageWithValidData() {
        $url = 'https://your-jira-instance.atlassian.net/rest/api/3/log';
        $token = 'YOUR_JIRA_TOKEN';

        // Criar instância do logger
        $jiraLogger = new JiraLogger($url, $token);

        // Log message with valid data
        $message = "Este é um exemplo de log enviado pelo PHP Agent para Jira.";
        $result = $jiraLogger->logMessage($message);

        // Assert that the response is not empty
        $this->assertNotEmpty($result);
    }

    public function testLogMessageWithInvalidData() {
        $url = 'https://your-jira-instance.atlassian.net/rest/api/3/log';
        $token = 'YOUR_JIRA_TOKEN';

        // Criar instância do logger
        $jiraLogger = new JiraLogger($url, $token);

        // Log message with invalid data (null value)
        $message = null;
        $result = $jiraLogger->logMessage($message);

        // Assert that the response is not empty
        $this->assertNotEmpty($result);
    }

    public function testLogMessageWithDivisionByZero() {
        $url = 'https://your-jira-instance.atlassian.net/rest/api/3/log';
        $token = 'YOUR_JIRA_TOKEN';

        // Criar instância do logger
        $jiraLogger = new JiraLogger($url, $token);

        // Log message with division by zero (null value)
        $message = "1 / 0";
        $result = $jiraLogger->logMessage($message);

        // Assert that the response is not empty
        $this->assertNotEmpty($result);
    }
}