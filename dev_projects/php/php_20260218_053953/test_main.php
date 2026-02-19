<?php

use PHPUnit\Framework\TestCase;

class PhpAgentTest extends TestCase {
    private $agent;

    protected function setUp(): void {
        $this->agent = new PhpAgent('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');
    }

    public function testCreateIssueWithValidData() {
        $summary = 'Teste de PHP Agent com Jira';
        $description = 'Este é um teste para integrar o PHP Agent com Jira.';
        $response = $this->agent->createIssue($summary, $description);
        $this->assertStringContains('Issue created with ID', $response);
    }

    public function testCreateIssueWithInvalidData() {
        $summary = '';
        $description = 'Este é um teste para integrar o PHP Agent com Jira.';
        $response = $this->agent->createIssue($summary, $description);
        $this->assertStringContains('Error creating issue', $response);
    }

    public function testUpdateIssueStatusWithValidData() {
        $status = 'In Progress';
        $response = $this->agent->updateIssueStatus($status);
        $this->assertStringContains('Issue status updated to', $response);
    }

    public function testUpdateIssueStatusWithInvalidData() {
        $status = '';
        $response = $this->agent->updateIssueStatus($status);
        $this->assertStringContains('Error updating issue status', $response);
    }
}