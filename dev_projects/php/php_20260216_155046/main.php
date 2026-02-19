<?php

// Importar as classes necessárias do PHP Agent
require_once 'vendor/autoload.php';

class JiraClient {
    private $baseUrl;
    private $token;

    public function __construct($baseUrl, $token) {
        $this->baseUrl = $baseUrl;
        $this->token = $token;
    }

    public function createIssue($projectKey, $summary, $description) {
        // Implementar a lógica para criar um issue no Jira
        // Você pode usar o PHP Agent para fazer requisições HTTP ao Jira API
        // Exemplo:
        // $response = $this->sendRequest('POST', '/rest/api/2/issue', [
        //     'Content-Type' => 'application/json',
        //     'Authorization' => "Bearer {$this->token}",
        //     'body' => json_encode([
        //         'fields' => [
        //             'project' => ['key' => $projectKey],
        //             'summary' => $summary,
        //             'description' => $description
        //         ]
        //     ])
        // ]);
        // return json_decode($response->getBody(), true);
    }

    private function sendRequest($method, $endpoint, $headers = [], $body = null) {
        $client = new GuzzleHttp\Client();
        $options = [
            'http' => [
                'method' => $method,
                'headers' => array_merge([
                    'Content-Type' => 'application/json',
                    'Authorization' => "Bearer {$this->token}"
                ], $headers),
                'body' => json_encode($body)
            ]
        ];

        return $client->request('POST', $endpoint, $options);
    }
}

// Configuração do PHP Agent
$baseUrl = 'https://your-jira-instance.atlassian.net';
$token = 'your-jira-token';

// Criar uma instância do JiraClient
$jiraClient = new JiraClient($baseUrl, $token);

// Exemplo de uso: criar um issue
$projectKey = 'YOUR_PROJECT_KEY';
$summary = 'New Feature Request';
$description = 'This is a new feature request for the application.';

try {
    $issueData = $jiraClient->createIssue($projectKey, $summary, $description);
    echo "Issue created successfully: " . json_encode($issueData);
} catch (Exception $e) {
    echo "Error creating issue: " . $e->getMessage();
}