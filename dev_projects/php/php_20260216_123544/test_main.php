<?php

use PHPUnit\Framework\TestCase;

class JiraClientTest extends TestCase {
    private $jiraClient;

    protected function setUp(): void {
        $this->jiraClient = new JiraClient('https://your_jira_instance.com/rest/api/2', 'your_jira_token');
    }

    public function testCreateIssue() {
        // Caso de sucesso com valores válidos
        $issueData = [
            'project' => ['key' => 'YOUR_PROJECT_KEY'],
            'summary' => 'New Issue',
            'description' => 'Description of the new issue',
            'issuetype' => ['name' => 'Bug']
        ];
        $response = $this->jiraClient->createIssue($issueData);
        $this->assertNotEmpty($response['id']);
    }

    public function testCreateIssueWithInvalidProjectKey() {
        // Caso de erro com valores inválidos
        $issueData = [
            'project' => ['key' => 'INVALID_PROJECT_KEY'],
            'summary' => 'New Issue',
            'description' => 'Description of the new issue',
            'issuetype' => ['name' => 'Bug']
        ];
        try {
            $this->jiraClient->createIssue($issueData);
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            $this->assertEquals('Invalid project key', $e->getMessage());
        }
    }

    public function testCreateIssueWithEmptySummary() {
        // Caso de erro com valores inválidos
        $issueData = [
            'project' => ['key' => 'YOUR_PROJECT_KEY'],
            'summary' => '',
            'description' => 'Description of the new issue',
            'issuetype' => ['name' => 'Bug']
        ];
        try {
            $this->jiraClient->createIssue($issueData);
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            $this->assertEquals('Summary cannot be empty', $e->getMessage());
        }
    }

    public function testCreateIssueWithInvalidDescription() {
        // Caso de erro com valores inválidos
        $issueData = [
            'project' => ['key' => 'YOUR_PROJECT_KEY'],
            'summary' => 'New Issue',
            'description' => '',
            'issuetype' => ['name' => 'Bug']
        ];
        try {
            $this->jiraClient->createIssue($issueData);
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            $this->assertEquals('Description cannot be empty', $e->getMessage());
        }
    }

    public function testCreateIssueWithInvalidIssuetype() {
        // Caso de erro com valores inválidos
        $issueData = [
            'project' => ['key' => 'YOUR_PROJECT_KEY'],
            'summary' => 'New Issue',
            'description' => 'Description of the new issue',
            'issuetype' => ['name' => 'INVALID_ISSUE_TYPE']
        ];
        try {
            $this->jiraClient->createIssue($issueData);
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            $this->assertEquals('Invalid issue type', $e->getMessage());
        }
    }

    public function testTrackTask() {
        // Caso de sucesso com valores válidos
        $taskData = [
            'name' => 'Task 1',
            'description' => 'Description of Task 1'
        ];
        $taskId = $this->phpAgent->trackTask($taskData['name'], 'In Progress');
        $response = $this->jiraClient->getIssue($taskId);
        $this->assertNotEmpty($response['id']);
    }

    public function testTrackTaskWithInvalidTaskId() {
        // Caso de erro com valores inválidos
        $taskData = [
            'name' => 'Task 1',
            'description' => 'Description of Task 1'
        ];
        try {
            $this->jiraClient->trackTask($taskData['name'], 'Invalid Status');
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            $this->assertEquals('Invalid task ID', $e->getMessage());
        }
    }

    public function testTrackTaskWithEmptyName() {
        // Caso de erro com valores inválidos
        $taskData = [
            'name' => '',
            'description' => 'Description of Task 1'
        ];
        try {
            $this->jiraClient->trackTask($taskData['name'], 'In Progress');
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            $this->assertEquals('Name cannot be empty', $e->getMessage());
        }
    }

    public function testTrackTaskWithInvalidStatus() {
        // Caso de erro com valores inválidos
        $taskData = [
            'name' => 'Task 1',
            'description' => 'Description of Task 1'
        ];
        try {
            $this->jiraClient->trackTask($taskData['name'], 'Invalid Status');
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            $this->assertEquals('Status cannot be empty', $e->getMessage());
        }
    }

    public function testGetIssue() {
        // Caso de sucesso com valores válidos
        $issueData = [
            'project' => ['key' => 'YOUR_PROJECT_KEY'],
            'summary' => 'New Issue',
            'description' => 'Description of the new issue',
            'issuetype' => ['name' => 'Bug']
        ];
        $taskId = $this->jiraClient->createIssue($issueData);
        $response = $this->jiraClient->getIssue($taskId);
        $this->assertNotEmpty($response['id']);
    }

    public function testGetIssueWithInvalidTaskId() {
        // Caso de erro com valores inválidos
        try {
            $this->jiraClient->getIssue('INVALID_TASK_ID');
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            $this->assertEquals('Invalid task ID', $e->getMessage());
        }
    }

    public function testGetIssueWithEmptySummary() {
        // Caso de erro com valores inválidos
        try {
            $this->jiraClient->getIssue('INVALID_TASK_ID');
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            $this->assertEquals('Summary cannot be empty', $e->getMessage());
        }
    }

    public function testGetIssueWithInvalidDescription() {
        // Caso de erro com valores inválidos
        try {
            $this->jiraClient->getIssue('INVALID_TASK_ID');
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            $this->assertEquals('Description cannot be empty', $e->getMessage());
        }
    }

    public function testGetIssueWithInvalidIssuetype() {
        // Caso de erro com valores inválidos
        try {
            $this->jiraClient->getIssue('INVALID_TASK_ID');
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            $this->assertEquals('Invalid issue type', $e->getMessage());
        }
    }
}