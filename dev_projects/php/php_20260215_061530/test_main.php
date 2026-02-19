<?php

use PHPUnit\Framework\TestCase;

class Scrum15Test extends TestCase {
    private $scrum15;

    public function setUp() {
        $this->scrum15 = new Scrum15('https://your-jira-instance.atlassian.net', 'YOUR_USERNAME', 'YOUR_PASSWORD');
    }

    public function testCreateIssueWithValidData() {
        $summary = 'Implement Scrum 15';
        $description = 'Implement the SCRUM 15 project';

        $this->scrum15->createIssue($summary, $description);

        // Verificar se a tarefa foi criada corretamente
        $issue = Issue::getById($this->scrum15->jiraClient, $this->scrum15->issueId);
        $this->assertEquals($summary, $issue['fields']['summary']);
        $this->assertEquals($description, $issue['fields']['description']);
    }

    public function testCreateIssueWithInvalidData() {
        // Teste com tarefa vazia
        try {
            $this->scrum15->createIssue('', '');
            $this->fail('Deveria lançar exceção');
        } catch (Exception $e) {
            $this->assertEquals('Summary and description cannot be empty', $e->getMessage());
        }

        // Teste com tarefa inválida
        try {
            $this->scrum15->createIssue('Invalid', 'Invalid');
            $this->fail('Deveria lançar exceção');
        } catch (Exception $e) {
            $this->assertEquals('Summary and description cannot be empty', $e->getMessage());
        }
    }

    public function testUpdateIssueWithValidData() {
        $status = 'In Progress';

        // Atualizar a tarefa para o status em andamento
        $this->scrum15->updateIssue($status);

        // Verificar se a tarefa foi atualizada corretamente
        $issue = Issue::getById($this->scrum15->jiraClient, $this->scrum15->issueId);
        $this->assertEquals($status, $issue['fields']['status']['name']);
    }

    public function testUpdateIssueWithInvalidData() {
        // Teste com tarefa vazia
        try {
            $this->scrum15->updateIssue('');
            $this->fail('Deveria lançar exceção');
        } catch (Exception $e) {
            $this->assertEquals('Status cannot be empty', $e->getMessage());
        }

        // Teste com tarefa inválida
        try {
            $this->scrum15->updateIssue('Invalid');
            $this->fail('Deveria lançar exceção');
        } catch (Exception $e) {
            $this->assertEquals('Status cannot be empty', $e->getMessage());
        }
    }

    public function testMain() {
        // Teste da função main
        $this->scrum15->main();

        // Verificar se a tarefa foi criada corretamente
        $issue = Issue::getById($this->scrum15->jiraClient, $this->scrum15->issueId);
        $this->assertEquals('Implement Scrum 15', $issue['fields']['summary']);
        $this->assertEquals('Implement the SCRUM 15 project', $issue['fields']['description']);

        // Verificar se a tarefa foi atualizada corretamente
        $issue = Issue::getById($this->scrum15->jiraClient, $this->scrum15->issueId);
        $this->assertEquals('In Progress', $issue['fields']['status']['name']);
    }
}