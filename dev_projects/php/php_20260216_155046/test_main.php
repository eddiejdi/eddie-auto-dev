<?php

use PHPUnit\Framework\TestCase;

class JiraClientTest extends TestCase {
    private $jiraClient;
    private $baseUrl = 'https://your-jira-instance.atlassian.net';
    private $token = 'your-jira-token';

    public function setUp() {
        $this->jiraClient = new JiraClient($this->baseUrl, $this->token);
    }

    public function testCreateIssueSuccess() {
        // Caso de sucesso com valores válidos
        $projectKey = 'YOUR_PROJECT_KEY';
        $summary = 'New Feature Request';
        $description = 'This is a new feature request for the application.';

        try {
            $issueData = $this->jiraClient->createIssue($projectKey, $summary, $description);
            $this->assertArrayHasKey('id', $issueData); // Verifica se o issue foi criado com um ID
            echo "Issue created successfully: " . json_encode($issueData);
        } catch (Exception $e) {
            $this->fail("Error creating issue: " . $e->getMessage());
        }
    }

    public function testCreateIssueFailure() {
        // Caso de erro (divisão por zero, valores inválidos, etc)
        $projectKey = 'YOUR_PROJECT_KEY';
        $summary = 'New Feature Request';
        $description = '';

        try {
            $issueData = $this->jiraClient->createIssue($projectKey, $summary, $description);
            $this->fail("Error creating issue: " . json_encode($issueData));
        } catch (Exception $e) {
            // Verifica se o erro é do tipo esperado
            $this->assertInstanceOf(Exception::class, $e);
            echo "Error creating issue: " . $e->getMessage();
        }
    }

    public function testCreateIssueEdgeCase() {
        // Edge cases (valores limite, strings vazias, None, etc)
        $projectKey = 'YOUR_PROJECT_KEY';
        $summary = 'New Feature Request';
        $description = null;

        try {
            $issueData = $this->jiraClient->createIssue($projectKey, $summary, $description);
            $this->assertArrayHasKey('id', $issueData); // Verifica se o issue foi criado com um ID
            echo "Issue created successfully: " . json_encode($issueData);
        } catch (Exception $e) {
            $this->fail("Error creating issue: " . $e->getMessage());
        }
    }
}