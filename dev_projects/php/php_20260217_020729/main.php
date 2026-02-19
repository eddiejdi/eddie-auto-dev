<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\JiraClient;
use PhpAgent\Task;

class JiraScrum15 {
    private $jiraClient;

    public function __construct($url, $username, $password) {
        $this->jiraClient = new JiraClient($url, $username, $password);
    }

    public function monitorarAtividades() {
        try {
            // Obter todas as tarefas da equipe
            $tasks = $this->jiraClient->getTasks();

            // Exibir informações sobre cada tarefa
            foreach ($tasks as $task) {
                echo "Título: {$task->getTitle()} - Status: {$task->getStatus()} - Prioridade: {$task->getPriority()}\n";
            }
        } catch (Exception $e) {
            echo "Erro ao monitorar atividades: {$e->getMessage()}\n";
        }
    }

    public function gerenciarTarefas($taskId, $status, $priority) {
        try {
            // Obter a tarefa específica
            $task = $this->jiraClient->getTask($taskId);

            // Atualizar o status e prioridade da tarefa
            $updatedTask = new Task(
                $task->getKey(),
                $status,
                $priority
            );

            // Salvar as alterações na tarefa
            $this->jiraClient->updateTask($updatedTask);
            echo "Tarefa {$taskId} atualizada com sucesso.\n";
        } catch (Exception $e) {
            echo "Erro ao gerenciar tarefas: {$e->getMessage()}\n";
        }
    }

    public static function main() {
        // Configuração do Jira
        $url = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Criar uma instância da classe JiraScrum15
        $jiraScrum15 = new JiraScrum15($url, $username, $password);

        // Monitorar atividades
        $jiraScrum15->monitorarAtividades();

        // Gerenciar tarefas (exemplo: atualizar a tarefa com ID 1234)
        $taskId = '1234';
        $status = 'In Progress';
        $priority = 'High';
        $jiraScrum15->gerenciarTarefas($taskId, $status, $priority);
    }
}

// Executar o script
if (__name__ == "__main__") {
    JiraScrum15::main();
}