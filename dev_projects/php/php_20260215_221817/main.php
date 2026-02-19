<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Jira\Client;

class Scrum15 {
    private $client;
    private $issueKey;

    public function __construct(string $jiraUrl, string $username, string $password) {
        $this->client = new Client($jiraUrl, $username, $password);
    }

    public function setIssueKey(string $issueKey) {
        $this->issueKey = $issueKey;
    }

    public function createIssue($summary, $description) {
        $issueData = [
            'fields' => [
                'project' => ['key' => 'YOUR_PROJECT_KEY'],
                'summary' => $summary,
                'description' => $description,
                'issuetype' => ['name' => 'Task']
            ]
        ];

        return $this->client->createIssue($issueData);
    }

    public function updateIssue(string $comment) {
        $updateData = [
            'fields' => [
                'comment' => [
                    'body' => $comment
                ]
            ]
        ];

        return $this->client->updateIssue($this->issueKey, $updateData);
    }

    public function closeIssue() {
        $updateData = [
            'fields' => [
                'status' => ['name' => 'Closed']
            ]
        ];

        return $this->client->updateIssue($this->issueKey, $updateData);
    }
}

// Função principal
function main() {
    // Configurações do Jira
    $jiraUrl = 'https://your-jira-instance.atlassian.net';
    $username = 'your-username';
    $password = 'your-password';

    // Criar uma instância da classe Scrum15
    $scrum15 = new Scrum15($jiraUrl, $username, $password);

    // Definir o issueKey
    $issueKey = 'YOUR_ISSUE_KEY';

    // Criar um novo issue
    $summary = 'New task';
    $description = 'This is a new task created using PHP Agent.';
    $createdIssue = $scrum15->createIssue($summary, $description);

    echo "Created issue: " . $createdIssue['key'] . "\n";

    // Atualizar o issue com um comentário
    $comment = 'Task completed successfully.';
    $updatedIssue = $scrum15->updateIssue($comment);

    echo "Updated issue: " . $updatedIssue['key'] . "\n";

    // Fechar o issue
    $scrum15->closeIssue();
}

// Executar a função main()
if (__name__ == "__main__") {
    main();
}