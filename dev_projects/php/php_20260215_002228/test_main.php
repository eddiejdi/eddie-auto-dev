<?php

use PHPUnit\Framework\TestCase;
use PhpAgent\Agent;
use PhpAgent\Exception\AgentException;

class JiraIntegrationTest extends TestCase {
    private $jiraApiUrl = 'https://your-jira-instance.com';
    private $username = 'your-username';
    private $password = 'your-password';
    private $projectKey = 'YOUR_PROJECT_KEY';

    public function setUp() {
        // Initialize the Jira integration object
        $this->jiraIntegration = new JiraIntegration($this->jiraApiUrl, $this->username, $this->password, $this->projectKey);
    }

    public function testCreateIssueSuccess() {
        $issueData = [
            'fields' => [
                'project' => ['key' => $this->projectKey],
                'summary' => 'Example issue',
                'description' => 'This is an example issue created using PHP Agent and Jira API.',
                'issuetype' => ['name' => 'Bug']
            ]
        ];

        try {
            $issue = $this->jiraIntegration->createIssue($issueData);
            $this->assertNotEmpty($issue, "Issue should be created successfully");
            $this->assertEquals('Bug', $issue['fields']['issuetype']['name'], "Issue type should be 'Bug'");
        } catch (Exception $e) {
            $this->fail("Failed to create issue: " . $e->getMessage());
        }
    }

    public function testCreateIssueFailure() {
        // Test creating an issue with invalid data
        $issueData = [
            'fields' => [
                'project' => ['key' => 'INVALID_PROJECT_KEY'],
                'summary' => '',
                'description' => 'This is an example issue created using PHP Agent and Jira API.',
                'issuetype' => ['name' => 'Bug']
            ]
        ];

        try {
            $this->jiraIntegration->createIssue($issueData);
            $this->fail("Expected an exception to be thrown for invalid data");
        } catch (Exception $e) {
            // Expected behavior: an exception should be thrown
        }
    }

    public function testUpdateIssueSuccess() {
        $issueKey = '12345';
        $updateData = [
            'fields' => [
                'summary' => 'Updated issue summary',
                'description' => 'This is the updated description for the issue.'
            ]
        ];

        try {
            $response = $this->jiraIntegration->updateIssue($issueKey, $updateData);
            $this->assertNotEmpty($response, "Update should be successful");
            $this->assertEquals('Updated issue summary', $response['fields']['summary'], "Summary should be updated");
        } catch (Exception $e) {
            $this->fail("Failed to update issue: " . $e->getMessage());
        }
    }

    public function testUpdateIssueFailure() {
        // Test updating an issue with invalid data
        $issueKey = '12345';
        $updateData = [
            'fields' => [
                'summary' => '',
                'description' => ''
            ]
        ];

        try {
            $this->jiraIntegration->updateIssue($issueKey, $updateData);
            $this->fail("Expected an exception to be thrown for invalid data");
        } catch (Exception $e) {
            // Expected behavior: an exception should be thrown
        }
    }

    public function testGetIssueSuccess() {
        $issueKey = '12345';

        try {
            $response = $this->jiraIntegration->getIssue($issueKey);
            $this->assertNotEmpty($response, "Issue should be retrieved successfully");
            $this->assertEquals('Bug', $response['fields']['issuetype']['name'], "Issue type should be 'Bug'");
        } catch (Exception $e) {
            $this->fail("Failed to get issue: " . $e->getMessage());
        }
    }

    public function testGetIssueFailure() {
        // Test getting an issue with invalid data
        $issueKey = 'INVALID_ISSUE_KEY';

        try {
            $response = $this->jiraIntegration->getIssue($issueKey);
            $this->fail("Expected an exception to be thrown for invalid data");
        } catch (Exception $e) {
            // Expected behavior: an exception should be thrown
        }
    }

    public function testDeleteIssueSuccess() {
        $issueKey = '12345';

        try {
            $response = $this->jiraIntegration->deleteIssue($issueKey);
            $this->assertNotEmpty($response, "Issue should be deleted successfully");
            $this->assertEquals('success', $response['error']['code'], "Error code should be 'success'");
        } catch (Exception $e) {
            $this->fail("Failed to delete issue: " . $e->getMessage());
        }
    }

    public function testDeleteIssueFailure() {
        // Test deleting an issue with invalid data
        $issueKey = 'INVALID_ISSUE_KEY';

        try {
            $response = $this->jiraIntegration->deleteIssue($issueKey);
            $this->fail("Expected an exception to be thrown for invalid data");
        } catch (Exception $e) {
            // Expected behavior: an exception should be thrown
        }
    }
}