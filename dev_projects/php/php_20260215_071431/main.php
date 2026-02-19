<?php

// Importar classes necessárias
require 'vendor/autoload.php';

use PhpAgent\Agent;
use PhpAgent\Jira;

class JiraTracker {
    private $jira;
    private $agent;

    public function __construct($url, $username, $password) {
        // Configurar o PHP Agent
        $this->agent = new Agent();
        $this->agent->setHost($url);
        $this->agent->setUsername($username);
        $this->agent->setPassword($password);

        // Configurar o Jira
        $this->jira = new Jira($this->agent);
    }

    public function trackTask($taskId, $status) {
        try {
            // Atualizar o status da tarefa no Jira
            $task = $this->jira->getTask($taskId);
            if ($task) {
                $updatedTask = $this->jira->updateTask($taskId, ['status' => $status]);
                echo "Tarefa {$taskId} atualizada para {$status}\n";
            } else {
                echo "Tarefa {$taskId} não encontrada\n";
            }
        } catch (\Exception $e) {
            echo "Erro ao atualizar tarefa: " . $e->getMessage() . "\n";
        }
    }

    public static function main($argv) {
        if (count($argv) != 3) {
            echo "Uso: php jira-tracker.php <url> <username> <password>\n";
            return;
        }

        $url = $argv[1];
        $username = $argv[2];
        $password = $argv[3];

        $tracker = new JiraTracker($url, $username, $password);
        $taskId = '12345'; // ID da tarefa a ser atualizada
        $status = 'In Progress'; // Novo status da tarefa

        $tracker->trackTask($taskId, $status);
    }
}

if (__name__ == "__main__") {
    JiraTracker::main($_SERVER['argv']);
}