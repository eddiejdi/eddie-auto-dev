<?php

use PHPUnit\Framework\TestCase;

class JiraApiTest extends TestCase {

    public function testAuthenticate() {
        $jiraUrl = 'https://your-jira-instance.com';
        $jiraUsername = 'your-username';
        $jiraPassword = 'your-password';

        // Autenticação com o Jira API
        $sessionToken = authenticate($jiraUrl, $jiraUsername, $jiraPassword);

        // Verificar se a autenticação foi bem-sucedida
        $this->assertNotEmpty($sessionToken);
    }

    public function testCreateTask() {
        $jiraUrl = 'https://your-jira-instance.com';
        $sessionToken = authenticate($jiraUrl, 'your-username', 'your-password');
        $projectKey = 'YOUR-PROJECT-KEY';
        $summary = 'Test Task';

        // Criar uma nova tarefa no Jira
        $response = createTask($jiraUrl, $sessionToken, $projectKey, $summary);

        // Verificar se a criação da tarefa foi bem-sucedida
        $this->assertNotEmpty($response['id']);
    }

    public function testListTasks() {
        $jiraUrl = 'https://your-jira-instance.com';
        $sessionToken = authenticate($jiraUrl, 'your-username', 'your-password');
        $projectKey = 'YOUR-PROJECT-KEY';

        // Listar todas as tarefas do projeto no Jira
        $response = listTasks($jiraUrl, $sessionToken, $projectKey);

        // Verificar se a lista de tarefas foi bem-sucedida
        $this->assertNotEmpty($response['issues']);
    }
}