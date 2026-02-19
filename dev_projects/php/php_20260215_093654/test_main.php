<?php

use PHPUnit\Framework\TestCase;

class TaskTest extends TestCase {
    public function testCreateTask() {
        // Configurações do Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Criar uma instância da integração com Jira
        $jiraIntegration = new JiraIntegration($jiraUrl, $username, $password);

        // Criar uma tarefa
        $task = new Task(1, 'Implement PHP Agent with Jira', 'Track activities in PHP using PHP Agent and Jira.');
        $jiraIntegration->createTask($task);

        // Verificar se a tarefa foi criada corretamente
        $this->assertTrue($jiraIntegration->createTask($task));
    }

    public function testUpdateTaskStatus() {
        // Configurações do Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Criar uma instância da integração com Jira
        $jiraIntegration = new JiraIntegration($jiraUrl, $username, $password);

        // Criar uma tarefa
        $task = new Task(1, 'Implement PHP Agent with Jira', 'Track activities in PHP using PHP Agent and Jira.');
        $jiraIntegration->createTask($task);

        // Atualizar o status da tarefa para em progresso
        $taskId = 1;
        $status = 'In Progress';
        $jiraIntegration->updateTaskStatus($taskId, $status);

        // Verificar se o status foi atualizado corretamente
        $this->assertTrue($jiraIntegration->updateTaskStatus($taskId, $status));
    }
}