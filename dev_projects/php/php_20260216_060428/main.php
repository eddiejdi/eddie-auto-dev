<?php

// Importar classes necessárias
use PhpAgent\Agent;
use PhpAgent\Transport\Http;

class JiraIntegration {
    private $agent;
    private $jiraUrl;
    private $username;
    private $password;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraUrl = $jiraUrl;
        $this->username = $username;
        $this->password = $password;

        // Configurar o agente PHP Agent
        $agentConfig = [
            'url' => $this->jiraUrl,
            'transport' => new Http(),
            'auth' => [$this->username, $this->password],
        ];

        $this->agent = new Agent($agentConfig);
    }

    public function trackActivity($issueKey, $activityDescription) {
        try {
            // Criar um novo item de atividade no Jira
            $issueData = [
                'fields' => [
                    'summary' => "Activity on issue {$issueKey}",
                    'description' => $activityDescription,
                ],
            ];

            $response = $this->agent->post("rest/api/2/issue/{$issueKey}/comment", $issueData);
            if ($response['status_code'] == 201) {
                echo "Activity tracked successfully.\n";
            } else {
                echo "Failed to track activity: " . json_encode($response) . "\n";
            }
        } catch (Exception $e) {
            echo "Error tracking activity: " . $e->getMessage() . "\n";
        }
    }

    public static function main() {
        // Configurações do Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Criar uma instância da classe JiraIntegration
        $integration = new JiraIntegration($jiraUrl, $username, $password);

        // Exemplo de uso: Travar atividade em um issue específico
        $issueKey = 'ABC-123';
        $activityDescription = "This is a test activity.";
        $integration->trackActivity($issueKey, $activityDescription);
    }
}

// Executar o método main() se este arquivo for executado diretamente
if (__name__ == "__main__") {
    JiraIntegration::main();
}