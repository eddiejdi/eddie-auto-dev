<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use App\JiraClient;
use App\EventLogger;

class Scrum15 {
    private $jiraClient;
    private $eventLogger;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraClient = new JiraClient($jiraUrl, $username, $password);
        $this->eventLogger = new EventLogger();
    }

    public function startScrum() {
        // Iniciar o Scrum
        echo "Iniciando Scrum\n";

        // Monitorar atividades
        $this->monitorActivities();

        // Registrar eventos
        $this->logEvents();
    }

    private function monitorActivities() {
        try {
            // Obter todas as tarefas pendentes no Jira
            $tasks = $this->jiraClient->getTasks();

            foreach ($tasks as $task) {
                echo "Tarefa Pendente: {$task['summary']}\n";

                // Simular processamento da tarefa
                sleep(2);

                // Atualizar status da tarefa no Jira
                $this->jiraClient->updateTaskStatus($task['key'], 'In Progress');
            }

            echo "Tarefas monitoradas\n";
        } catch (Exception $e) {
            echo "Erro ao monitorar atividades: {$e->getMessage()}\n";
        }
    }

    private function logEvents() {
        try {
            // Simular registro de eventos
            sleep(1);

            // Logar evento de início do Scrum
            $this->eventLogger->logEvent('Scrum Iniciado');

            // Simular registro de eventos
            sleep(2);

            // Logar evento de monitoramento de atividades
            $this->eventLogger->logEvent('Monitoramento de Atividades');

            // Simular registro de eventos
            sleep(1);

            // Logar evento de registro detalhado de eventos
            $this->eventLogger->logEvent('Registro Detalhado de Eventos');
        } catch (Exception $e) {
            echo "Erro ao registrar eventos: {$e->getMessage()}\n";
        }
    }

    public static function main($argv) {
        if ($argc !== 4) {
            echo "Uso: php scrum15.php <jira-url> <username> <password>\n";
            return;
        }

        $jiraUrl = $argv[1];
        $username = $argv[2];
        $password = $argv[3];

        $scrum15 = new Scrum15($jiraUrl, $username, $password);
        $scrum15->startScrum();
    }
}

if (__name__ == "__main__") {
    Scrum15::main($_SERVER['argv']);
}