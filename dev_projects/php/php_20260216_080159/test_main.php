<?php

use PHPUnit\Framework\TestCase;

class PhpAgentJiraTest extends TestCase
{
    private $jiraUrl = 'https://your-jira-instance.atlassian.net';
    private $username = 'your-username';
    private $password = 'your-password';

    public function setUp()
    {
        // Configurações do PHP Agent Jira
        $this->agentJira = new PhpAgentJira($this->jiraUrl, $this->username, $this->password);
    }

    public function testCreateTaskSuccess()
    {
        // Título e descrição da tarefa
        $issueKey = 'YOUR_TASK_KEY';
        $summary = 'Task summary';
        $description = 'Task description';

        try {
            // Cria a tarefa no Jira
            $task = $this->agentJira->createTask($issueKey, $summary, $description);

            // Verifica se o retorno é um array e contém as propriedades esperadas
            $this->assertIsArray($task);
            $this->assertArrayHasKey('id', $task);
            $this->assertArrayHasKey('key', $task);
            $this->assertArrayHasKey('fields', $task);
        } catch (Exception $e) {
            $this->fail("Failed to create task: " . $e->getMessage());
        }
    }

    public function testCreateTaskError()
    {
        // Título e descrição da tarefa
        $issueKey = 'YOUR_TASK_KEY';
        $summary = '';
        $description = '';

        try {
            // Cria a tarefa no Jira
            $task = $this->agentJira->createTask($issueKey, $summary, $description);

            // Verifica se o retorno é um array e contém as propriedades esperadas
            $this->assertIsArray($task);
            $this->assertArrayHasKey('error', $task);
        } catch (Exception $e) {
            $this->assertEquals("Invalid summary or description", $e->getMessage());
        }
    }

    public function testCreateTaskEdgeCase()
    {
        // Título e descrição da tarefa
        $issueKey = 'YOUR_TASK_KEY';
        $summary = null;
        $description = '';

        try {
            // Cria a tarefa no Jira
            $task = $this->agentJira->createTask($issueKey, $summary, $description);

            // Verifica se o retorno é um array e contém as propriedades esperadas
            $this->assertIsArray($task);
            $this->assertArrayHasKey('error', $task);
        } catch (Exception $e) {
            $this->assertEquals("Invalid summary or description", $e->getMessage());
        }
    }
}