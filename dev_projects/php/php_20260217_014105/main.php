<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\PhpAgent;
use JiraApi\JiraApi;

class TaskTracker {
    private $agent;
    private $jiraApi;

    public function __construct($agentConfig, $jiraConfig) {
        // Inicializar PHP Agent
        $this->agent = new PhpAgent($agentConfig);
        $this->agent->start();

        // Inicializar Jira API
        $this->jiraApi = new JiraApi($jiraConfig);
    }

    public function addTask($title, $description) {
        try {
            // Criar tarefa no Jira
            $task = [
                'fields' => [
                    'project' => ['key' => 'YOUR_PROJECT_KEY'],
                    'summary' => $title,
                    'description' => $description,
                    'assignee' => ['name' => 'YOUR_USER_NAME']
                ]
            ];

            $response = $this->jiraApi->createIssue($task);
            echo "Task added successfully: " . json_encode($response, JSON_PRETTY_PRINT) . "\n";
        } catch (\Exception $e) {
            echo "Error adding task: " . $e->getMessage() . "\n";
        }
    }

    public function updateTask($taskId, $title, $description) {
        try {
            // Atualizar tarefa no Jira
            $task = [
                'fields' => [
                    'summary' => $title,
                    'description' => $description
                ]
            ];

            $response = $this->jiraApi->updateIssue($taskId, $task);
            echo "Task updated successfully: " . json_encode($response, JSON_PRETTY_PRINT) . "\n";
        } catch (\Exception $e) {
            echo "Error updating task: " . $e->getMessage() . "\n";
        }
    }

    public function deleteTask($taskId) {
        try {
            // Deletar tarefa no Jira
            $response = $this->jiraApi->deleteIssue($taskId);
            echo "Task deleted successfully: " . json_encode($response, JSON_PRETTY_PRINT) . "\n";
        } catch (\Exception $e) {
            echo "Error deleting task: " . $e->getMessage() . "\n";
        }
    }

    public function listTasks() {
        try {
            // Listar todas as tarefas no Jira
            $response = $this->jiraApi->getIssues();
            echo "Tasks listed successfully:\n" . json_encode($response, JSON_PRETTY_PRINT) . "\n";
        } catch (\Exception $e) {
            echo "Error listing tasks: " . $e->getMessage() . "\n";
        }
    }

    public function main() {
        // Configurações do PHP Agent
        $agentConfig = [
            'host' => 'localhost',
            'port' => 2000,
            'username' => 'YOUR_AGENT_USERNAME',
            'password' => 'YOUR_AGENT_PASSWORD'
        ];

        // Configurações do Jira API
        $jiraConfig = [
            'url' => 'https://your-jira-instance.atlassian.net/rest/api/3',
            'username' => 'YOUR_JIRA_USERNAME',
            'password' => 'YOUR_JIRA_PASSWORD'
        ];

        // Criar instância da classe TaskTracker
        $taskTracker = new TaskTracker($agentConfig, $jiraConfig);

        // Exemplos de uso das funções
        $taskTracker->addTask('Teste Tarefa', 'Descrição da tarefa');
        $taskTracker->updateTask(12345, 'Novo Título', 'Nova descrição da tarefa');
        $taskTracker->deleteTask(12345);
        $taskTracker->listTasks();
    }
}

if (__name__ == "__main__") {
    TaskTracker::main();
}