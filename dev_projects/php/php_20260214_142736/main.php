<?php

// Importar classes necessárias
use PhpAgent\Agent;
use PhpAgent\Exception\AgentException;

class JiraIntegration {
    private $agent;
    private $jiraUrl;
    private $username;
    private $password;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraUrl = $jiraUrl;
        $this->username = $username;
        $this->password = $password;
        $this->agent = new Agent();
    }

    public function trackActivity($issueKey, $activityType, $description) {
        try {
            // Autenticar com o Jira
            $this->agent->login($this->jiraUrl, $this->username, $this->password);

            // Criar a atividade no Jira
            $issue = $this->agent->createIssue(
                $issueKey,
                [
                    'fields' => [
                        'summary' => $description,
                        'issuetype' => [
                            'name' => $activityType
                        ]
                    ]
                ]
            );

            echo "Atividade criada com sucesso: " . json_encode($issue);
        } catch (AgentException $e) {
            echo "Erro ao integrar PHP Agent com Jira: " . $e->getMessage();
        }
    }

    public static function main() {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Criar uma instância da classe JiraIntegration
        $integration = new JiraIntegration($jiraUrl, $username, $password);

        // Exemplo de uso: criar atividade em um issue
        $issueKey = 'ABC-123';
        $activityType = 'Task';
        $description = 'Implementar o novo sistema';

        $integration->trackActivity($issueKey, $activityType, $description);
    }
}

// Executar o script se for CLI
if (__name__ == "__main__") {
    JiraIntegration::main();
}