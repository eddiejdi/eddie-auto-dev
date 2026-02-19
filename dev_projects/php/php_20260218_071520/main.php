<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Agent;
use PhpAgent\Client;

// Configuração do agente PHP Agent
$agent = new Agent([
    'name' => 'PHP Agent',
    'version' => '1.0.0',
]);

// Configuração do cliente Jira
$client = new Client('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

// Função para criar uma nova tarefa no Jira
function createTask($client, $title, $description) {
    try {
        $task = [
            'fields' => [
                'project' => ['key' => 'YOUR_PROJECT_KEY'],
                'summary' => $title,
                'description' => $description,
                'assignee' => ['name' => 'YOUR_USER_NAME'],
            ],
        ];

        $response = $client->post('rest/api/2/issue', json_encode($task));
        return json_decode($response, true);
    } catch (\Exception $e) {
        echo "Error creating task: " . $e->getMessage();
        return null;
    }
}

// Função para listar todas as tarefas do Jira
function listTasks($client) {
    try {
        $response = $client->get('rest/api/2/search', [
            'jql' => 'project = YOUR_PROJECT_KEY',
            'fields' => ['summary', 'description'],
        ]);
        return json_decode($response, true);
    } catch (\Exception $e) {
        echo "Error listing tasks: " . $e->getMessage();
        return null;
    }
}

// Função para atualizar uma tarefa no Jira
function updateTask($client, $issueKey, $title, $description) {
    try {
        $task = [
            'fields' => [
                'summary' => $title,
                'description' => $description,
            ],
        ];

        $response = $client->put("rest/api/2/issue/{$issueKey}", json_encode($task));
        return json_decode($response, true);
    } catch (\Exception $e) {
        echo "Error updating task: " . $e->getMessage();
        return null;
    }
}

// Função para deletar uma tarefa no Jira
function deleteTask($client, $issueKey) {
    try {
        $response = $client->delete("rest/api/2/issue/{$issueKey}");
        return json_decode($response, true);
    } catch (\Exception $e) {
        echo "Error deleting task: " . $e->getMessage();
        return null;
    }
}

// Função principal
function main() {
    // Configurar o agente PHP Agent
    $agent = new Agent([
        'name' => 'PHP Agent',
        'version' => '1.0.0',
    ]);

    // Conectar ao cliente Jira
    $client = new Client('https://your-jira-instance.atlassian.net', 'your-username', 'your-password');

    // Criar uma nova tarefa
    $task = createTask($client, 'Test Task', 'This is a test task for the PHP Agent.');
    if ($task) {
        echo "Task created successfully: " . json_encode($task);
    }

    // Listar todas as tarefas
    $tasks = listTasks($client);
    if ($tasks) {
        echo "Tasks listed successfully: " . json_encode($tasks);
    }

    // Atualizar uma tarefa
    $updatedTask = updateTask($client, 'TASK-123', 'Updated Test Task', 'This is an updated test task for the PHP Agent.');
    if ($updatedTask) {
        echo "Task updated successfully: " . json_encode($updatedTask);
    }

    // Deletar uma tarefa
    $deletedTask = deleteTask($client, 'TASK-123');
    if ($deletedTask) {
        echo "Task deleted successfully.";
    }
}

// Executar a função principal
if (__name__ == "__main__") {
    main();
}