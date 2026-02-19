<?php

use PHPUnit\Framework\TestCase;
use PhpAgent\PhpAgent;
use PhpAgent\Jira\JiraClient;

class JiraIntegrationTest extends TestCase
{
    public function setUp()
    {
        // Configurar o cliente Jira
        $this->jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        $this->integration = new JiraIntegration($this->jiraUrl, $username, $password);
    }

    public function testTrackIssueSuccess()
    {
        // Caso de sucesso com valores válidos
        $issueKey = 'ABC-123';
        $status = 'In Progress';

        try {
            $this->integration->trackIssue($issueKey, $status);

            $this->assertEquals("Issue {$issueKey} updated to {$status}", $output);
        } catch (\Exception $e) {
            $this->fail("Error updating issue: " . $e->getMessage());
        }
    }

    public function testTrackIssueFailure()
    {
        // Caso de erro (divisão por zero)
        $issueKey = 'ABC-123';
        $status = 'In Progress';

        try {
            $this->integration->trackIssue($issueKey, $status);

            $this->fail("Error updating issue: Division by zero");
        } catch (\Exception $e) {
            $this->assertEquals("Error updating issue: Division by zero", $output);
        }
    }

    public function testLogEventSuccess()
    {
        // Caso de sucesso com valores válidos
        $issueKey = 'ABC-123';
        $event = 'Task Started';

        try {
            $this->integration->logEvent($issueKey, $event);

            $this->assertEquals("Event logged for issue {$issueKey}", $output);
        } catch (\Exception $e) {
            $this->fail("Error logging event: " . $e->getMessage());
        }
    }

    public function testLogEventFailure()
    {
        // Caso de erro (divisão por zero)
        $issueKey = 'ABC-123';
        $event = 'Task Started';

        try {
            $this->integration->logEvent($issueKey, $event);

            $this->fail("Error logging event: Division by zero");
        } catch (\Exception $e) {
            $this->assertEquals("Error logging event: Division by zero", $output);
        }
    }

    public function testMain()
    {
        // Caso de uso
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        try {
            $this->integration->main();

            $this->assertEquals("Issue ABC-123 updated to In Progress", $output);
            $this->assertEquals("Event logged for issue ABC-123", $output);
        } catch (\Exception $e) {
            $this->fail("Error running main method: " . $e->getMessage());
        }
    }
}