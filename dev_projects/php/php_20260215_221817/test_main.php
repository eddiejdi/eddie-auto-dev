<?php

use PhpAgent\Jira\Client;

class Scrum15Test extends TestCase {
    private $scrum15;
    private $issueKey;

    public function setUp(): void {
        parent::setUp();
        $this->jiraUrl = 'https://your-jira-instance.atlassian.net';
        $this->username = 'your-username';
        $this->password = 'your-password';

        // Criar uma instância da classe Scrum15
        $this->scrum15 = new Scrum15($this->jiraUrl, $this->username, $this->password);

        // Definir o issueKey
        $this->issueKey = 'YOUR_ISSUE_KEY';
    }

    public function testCreateIssue() {
        $summary = 'New task';
        $description = 'This is a new task created using PHP Agent.';
        $createdIssue = $this->scrum15->createIssue($summary, $description);

        // Verificar se o issue foi criado corretamente
        $this->assertNotEmpty($createdIssue['key']);
    }

    public function testUpdateIssue() {
        $comment = 'Task completed successfully.';
        $updatedIssue = $this->scrum15->updateIssue($comment);

        // Verificar se o issue foi atualizado corretamente
        $this->assertNotEmpty($updatedIssue['key']);
    }

    public function testCloseIssue() {
        $closeResult = $this->scrum15->closeIssue();

        // Verificar se o issue foi fechado corretamente
        $this->assertTrue($closeResult);
    }
}