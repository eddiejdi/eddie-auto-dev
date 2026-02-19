<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use Jira\Client;
use Jira\Issue;

class Scrum15 {
    private $jiraClient;
    private $issueId;
    private $activityLog;

    public function __construct($jiraUrl, $username, $password, $issueId) {
        // Configurar o cliente do Jira
        $this->jiraClient = new Client([
            'url' => $jiraUrl,
            'auth' => [$username, $password]
        ]);

        // Registrar o ID da tarefa
        $this->issueId = $issueId;

        // Inicializar a log de atividades
        $this->activityLog = [];
    }

    public function registerActivity($activity) {
        // Adicionar a atividade à log
        $this->activityLog[] = $activity;
    }

    public function monitorActivities() {
        // Monitorar as atividades da tarefa e registrar no Jira
        foreach ($this->activityLog as $activity) {
            $issue = new Issue($this->jiraClient, $this->issueId);
            $issue->update([
                'fields' => [
                    'description' => $activity
                ]
            ]);
        }
    }

    public static function main() {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';
        $issueId = 'YOUR-ISSUE-ID';

        // Criar uma instância da classe Scrum15
        $scrum15 = new Scrum15($jiraUrl, $username, $password, $issueId);

        // Registrar algumas atividades
        $scrum15->registerActivity('Tarefa iniciada');
        $scrum15->registerActivity('Processamento de dados');

        // Monitorar as atividades da tarefa
        $scrum15->monitorActivities();
    }
}

// Executar o script principal
Scrum15::main();