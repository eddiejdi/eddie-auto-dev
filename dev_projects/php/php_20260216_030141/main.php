<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

// Classe para integrar PHP Agent com Jira
class PhpAgentJira {
    private $jiraUrl;
    private $username;
    private $password;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraUrl = $jiraUrl;
        $this->username = $username;
        $this->password = $password;
    }

    // Função para criar um ticket no Jira
    public function createTicket($summary, $description) {
        $url = $this->jiraUrl . '/rest/api/2/issue';
        $headers = [
            'Content-Type: application/json',
            'Authorization: Basic ' . base64_encode("$this->username:$this->password")
        ];

        $data = json_encode([
            "fields" => [
                "project": {
                    "key": "YOUR_PROJECT_KEY"
                },
                "summary": $summary,
                "description": $description,
                "issuetype": {
                    "name": "Task"
                }
            ]
        ]);

        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

        $response = curl_exec($ch);
        curl_close($ch);

        return json_decode($response, true);
    }
}

// Função principal do programa
function main() {
    // Configurações do PHP Agent Jira
    $jiraUrl = 'https://your-jira-instance.atlassian.net';
    $username = 'your-username';
    $password = 'your-password';

    // Instanciar a classe PhpAgentJira
    $phpAgentJira = new PhpAgentJira($jiraUrl, $username, $password);

    // Criar um ticket no Jira
    $summary = "Teste de PHP Agent com Jira";
    $description = "Este é um teste para verificar a integração do PHP Agent com Jira.";

    $ticket = $phpAgentJira->createTicket($summary, $description);

    if ($ticket['id']) {
        echo "Ticket criado com sucesso: {$ticket['id']}\n";
    } else {
        echo "Erro ao criar ticket: " . json_encode($ticket) . "\n";
    }
}

// Verificar se o script é executado como programa principal
if (__name__ == "__main__") {
    main();
}