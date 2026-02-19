<?php

use PhpAgent\Jira\JiraClient;
use PhpAgent\Jira\Issue;

class JiraTrackerTest extends PHPUnit\Framework\TestCase {

    protected $jiraUrl = 'https://your-jira-instance.atlassian.net';
    protected $username = 'your-username';
    protected $password = 'your-password';

    public function setUp() {
        $this->jiraClient = new JiraClient($this->jiraUrl, $this->username, $this->password);
    }

    public function testCreateIssueSuccess() {
        $projectKey = 'YOUR_PROJECT_KEY';
        $summary = 'Test issue';
        $description = 'This is a test issue created using PHP Agent with Jira';

        $result = $this->jiraTracker->createIssue($projectKey, $summary, $description);

        $this->assertEquals("Issue created successfully", $result);
    }

    public function testCreateIssueFailure() {
        $projectKey = 'YOUR_PROJECT_KEY';
        $summary = '';
        $description = '';

        $result = $this->jiraTracker->createIssue($projectKey, $summary, $description);

        $this->assertEquals("Error creating issue: Invalid summary or description", $result);
    }

    public function testUpdateIssueSuccess() {
        $issueKey = 'YOUR_ISSUE_KEY';
        $summary = 'Updated test issue';
        $description = 'This is an updated test issue created using PHP Agent with Jira';

        $this->jiraTracker->createIssue('YOUR_PROJECT_KEY', 'Test issue', 'This is a test issue created using PHP Agent with Jira');

        $result = $this->jiraTracker->updateIssue($issueKey, $summary, $description);

        $this->assertEquals("Issue updated successfully", $result);
    }

    public function testUpdateIssueFailure() {
        $issueKey = 'YOUR_ISSUE_KEY';
        $summary = '';
        $description = '';

        $this->jiraTracker->createIssue('YOUR_PROJECT_KEY', 'Test issue', 'This is a test issue created using PHP Agent with Jira');

        $result = $this->jiraTracker->updateIssue($issueKey, $summary, $description);

        $this->assertEquals("Error updating issue: Invalid summary or description", $result);
    }

    public function testDeleteIssueSuccess() {
        $issueKey = 'YOUR_ISSUE_KEY';
        $this->jiraTracker->createIssue('YOUR_PROJECT_KEY', 'Test issue', 'This is a test issue created using PHP Agent with Jira');

        $result = $this->jiraTracker->deleteIssue($issueKey);

        $this->assertEquals("Issue deleted successfully", $result);
    }

    public function testDeleteIssueFailure() {
        $issueKey = 'YOUR_ISSUE_KEY';

        $result = $this->jiraTracker->deleteIssue($issueKey);

        $this->assertEquals("Error deleting issue: Issue not found", $result);
    }
}