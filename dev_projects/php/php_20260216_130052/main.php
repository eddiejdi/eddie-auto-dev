<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\JiraClient;
use PhpAgent\EventLogger;

class JiraScrum15 {

    private $jiraClient;
    private $eventLogger;

    public function __construct($jiraUrl, $username, $password) {
        // Criar um cliente do Jira
        $this->jiraClient = new JiraClient($jiraUrl);
        $this->jiraClient->login($username, $password);

        // Criar um logger de eventos
        $this->eventLogger = new EventLogger();
    }

    public function monitorarAtividades() {
        try {
            // Listar todas as tarefas pendentes
            $tasks = $this->jiraClient->getTasks('open');

            foreach ($tasks as $task) {
                // Registrar o evento de atividade
                $this->eventLogger->logEvent($task);

                // Monitorar a situação da tarefa
                if ($task->getStatus() == 'in_progress') {
                    echo "Tarefa {$task->getKey()} está em progresso.\n";
                } else if ($task->getStatus() == 'completed') {
                    echo "Tarefa {$task->getKey()} foi concluída.\n";
                }
            }
        } catch (\Exception $e) {
            // Tratar erros
            echo "Erro ao monitorar atividades: " . $e->getMessage();
        }
    }

    public function registrarEventos() {
        try {
            // Listar todas as tarefas pendentes
            $tasks = $this->jiraClient->getTasks('open');

            foreach ($tasks as $task) {
                // Registrar o evento de atividade
                $this->eventLogger->logEvent($task);
            }
        } catch (\Exception $e) {
            // Tratar erros
            echo "Erro ao registrar eventos: " . $e->getMessage();
        }
    }

    public static function main() {
        // Configurar as credenciais do Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Criar uma instância da classe JiraScrum15
        $scrum15 = new JiraScrum15($jiraUrl, $username, $password);

        // Monitorar atividades
        $scrum15->monitorarAtividades();

        // Registrar eventos
        $scrum15->registrarEventos();
    }
}

// Executar o código principal
JiraScrum15::main();