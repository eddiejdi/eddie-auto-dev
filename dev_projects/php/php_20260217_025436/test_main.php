<?php

use PHPUnit\Framework\TestCase;

class ScrumBoardTest extends TestCase {
    private $scrumBoard;
    private $jiraClient;
    private $issueTracker;

    protected function setUp() {
        $this->jiraUrl = 'https://your-jira-instance.atlassian.net';
        $this->username = 'your-username';
        $this->password = 'your-password';

        $this->scrumBoard = new ScrumBoard($this->jiraUrl, $this->username, $this->password);
        $this->issueTracker = new IssueTracker($this->scrumBoard->client);
    }

    public function testCreateIssue() {
        $summary = 'Implement PHP Agent';
        $description = 'Tracking of activities in PHP';

        $issueId = $this->scrumBoard->createIssue($summary, $description);

        // Verificar se a issue foi criada com sucesso
        $createdIssue = $this->issueTracker->getIssueById($issueId);
        $this->assertNotEmpty($createdIssue);
    }

    public function testUpdateIssue() {
        $issueId = '12345'; // ID de uma issue existente no Jira
        $summary = 'Implement PHP Agent';
        $description = 'Tracking of activities in PHP with new features';

        $this->scrumBoard->updateIssue($issueId, $summary, $description);

        // Verificar se a issue foi atualizada com sucesso
        $updatedIssue = $this->issueTracker->getIssueById($issueId);
        $this->assertEquals($summary, $updatedIssue['fields']['summary']);
    }

    public function testGetIssues() {
        $issues = $this->scrumBoard->getIssues();

        // Verificar se a lista de issues não está vazia
        $this->assertNotEmpty($issues);

        // Verificar se o número de issues é igual ao esperado (por exemplo, 10)
        $this->assertEquals(10, count($issues));
    }
}