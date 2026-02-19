<?php

use PhpAgent\Jira\JiraClient;
use PhpAgent\Jira\Issue;

class Scrum15Test extends \PHPUnit\Framework\TestCase {

    protected $jiraUrl = 'https://your-jira-instance.com';
    protected $username = 'your-username';
    protected $password = 'your-password';

    public function setUp(): void {
        // Configuração do Jira
        $this->jiraClient = new JiraClient($this->jiraUrl, $this->username, $this->password);
    }

    public function testCreateIssueSuccess() {
        $issueData = [
            'summary' => 'New feature request',
            'description' => 'Implement a new feature in the application',
            'priority' => 'High',
            'assignee' => 'JohnDoe'
        ];
        $createdIssue = $this->jiraClient->createIssue($issueData);
        $this->assertNotEmpty($createdIssue, "Issue should be created successfully");
    }

    public function testCreateIssueError() {
        $issueData = [
            'summary' => '',
            'description' => 'Implement a new feature in the application',
            'priority' => 'High',
            'assignee' => null
        ];
        try {
            $this->jiraClient->createIssue($issueData);
            $this->fail("Error should be thrown when creating issue with empty summary");
        } catch (\Exception $e) {
            // Expected exception, no need to assert anything
        }
    }

    public function testUpdateIssueSuccess() {
        $issueData = [
            'summary' => 'New feature request',
            'description' => 'Implement a new feature in the application',
            'priority' => 'High',
            'assignee' => 'JohnDoe'
        ];
        $createdIssue = $this->jiraClient->createIssue($issueData);
        if ($createdIssue) {
            $updateData = [
                'description' => 'Update the feature request with new details',
                'priority' => 'Medium'
            ];
            $updatedIssue = $this->jiraClient->updateIssue($createdIssue->id, $updateData);
            $this->assertNotEmpty($updatedIssue, "Issue should be updated successfully");
        }
    }

    public function testUpdateIssueError() {
        $issueData = [
            'summary' => '',
            'description' => 'Implement a new feature in the application',
            'priority' => 'High',
            'assignee' => null
        ];
        try {
            $this->jiraClient->createIssue($issueData);
            $updateData = [
                'description' => '',
                'priority' => null
            ];
            $this->jiraClient->updateIssue($createdIssue->id, $updateData);
            $this->fail("Error should be thrown when updating issue with empty description");
        } catch (\Exception $e) {
            // Expected exception, no need to assert anything
        }
    }

    public function testDeleteIssueSuccess() {
        $issueData = [
            'summary' => 'New feature request',
            'description' => 'Implement a new feature in the application',
            'priority' => 'High',
            'assignee' => 'JohnDoe'
        ];
        $createdIssue = $this->jiraClient->createIssue($issueData);
        if ($createdIssue) {
            $deletedIssue = $this->jiraClient->deleteIssue($createdIssue->id);
            $this->assertTrue($deletedIssue, "Issue should be deleted successfully");
        }
    }

    public function testDeleteIssueError() {
        try {
            $this->jiraClient->deleteIssue('non-existing-issue-id');
            $this->fail("Error should be thrown when deleting non-existing issue");
        } catch (\Exception $e) {
            // Expected exception, no need to assert anything
        }
    }

    public static function main() {
        // Executar o script principal
        Scrum15::main();
    }
}