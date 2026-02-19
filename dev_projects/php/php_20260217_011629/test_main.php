<?php

// Importar classes necessárias
require 'vendor/autoload.php';

use PHPUnit\Framework\TestCase;

class PhpAgentTest extends TestCase {
    public function testCreateIssueSuccess() {
        // Configurar a conexão com Jira
        $jiraUrl = 'https://your-jira-instance.com';
        $jiraUsername = 'your-username';
        $jiraPassword = 'your-password';

        // Criar uma instância de PHP Agent
        $phpAgent = new \PhpAgent\Agent($jiraUrl, $jiraUsername, $jiraPassword);

        // Definir a tarefa que será registrada no Jira
        $taskTitle = 'Teste Tarefa';
        $taskDescription = 'Descrição da tarefa de teste';

        // Registrar a tarefa no Jira
        $result = $phpAgent->createIssue($taskTitle, $taskDescription);

        // Verificar se a tarefa foi registrada com sucesso
        $this->assertTrue($result);
    }

    public function testCreateIssueFailure() {
        // Configurar a conexão com Jira
        $jiraUrl = 'https://your-jira-instance.com';
        $jiraUsername = 'your-username';
        $jiraPassword = 'your-password';

        // Criar uma instância de PHP Agent
        $phpAgent = new \PhpAgent\Agent($jiraUrl, $jiraUsername, $jiraPassword);

        // Definir a tarefa que será registrada no Jira com valores inválidos
        $taskTitle = '';
        $taskDescription = '';

        // Registrar a tarefa no Jira
        $result = $phpAgent->createIssue($taskTitle, $taskDescription);

        // Verificar se o registro falhou
        $this->assertFalse($result);
    }
}