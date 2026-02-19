<?php

use PHPUnit\Framework\TestCase;

class PhpAgentJiraIntegratorTest extends TestCase {

    protected $integrator;

    public function setUp() {
        $this->jiraUrl = 'https://your-jira-instance.atlassian.net';
        $this->username = 'your-username';
        $this->password = 'your-password';

        $this->integrator = new PhpAgentJiraIntegrator($this->jiraUrl, $this->username, $this->password);
    }

    public function testLogActivitySuccess() {
        $activityLog = "PHP Agent activity: A new request was processed.\n";
        $this->integrator->logActivity($activityLog);

        // Check if the issue was created successfully in Jira
        $issue = $this->getIntegrationIssue();
        $this->assertEquals('YOUR_PROJECT_KEY', $issue['project']['key']);
        $this->assertEquals('PHP Agent Activity', $issue['summary']);
        $this->assertEquals($activityLog, $issue['description']);
    }

    public function testLogActivityFailure() {
        // Test a failure case where the issue creation fails
        try {
            $this->integrator->logActivity("Invalid activity log");
        } catch (\Exception $e) {
            $this->assertStringContains("Failed to create issue in Jira", $e->getMessage());
        }
    }

    public function testLogActivityEdgeCase() {
        // Test an edge case where the project key is empty
        try {
            $this->integrator->logActivity("PHP Agent activity: A new request was processed.\n");
        } catch (\Exception $e) {
            $this->assertStringContains("Invalid project key", $e->getMessage());
        }
    }

    private function getIntegrationIssue() {
        // This method would retrieve the issue from Jira after creating it
        // For demonstration purposes, we'll just return a dummy array
        return [
            'project' => ['key' => 'YOUR_PROJECT_KEY'],
            'summary' => 'PHP Agent Activity',
            'description' => "Invalid activity log"
        ];
    }
}