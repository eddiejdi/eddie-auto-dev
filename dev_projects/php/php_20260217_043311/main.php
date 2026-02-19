<?php

// Configuração do PHP Agent com Jira
define('PHP_AGENT_URL', 'http://jira.example.com/rest/api/2/issue');
define('PHP_AGENT_PROJECT_ID', '12345');

// Função para criar um novo issue no Jira
function createIssue($title, $description) {
    global $PHP_AGENT_URL, $PHP_AGENT_PROJECT_ID;

    $data = [
        'fields' => [
            'project' => ['key' => $PHP_AGENT_PROJECT_ID],
            'summary' => $title,
            'description' => $description,
            'issuetype' => ['name' => 'Task']
        ]
    ];

    $curl = curl_init();
    curl_setopt($curl, CURLOPT_URL, $PHP_AGENT_URL);
    curl_setopt($curl, CURLOPT_POST, true);
    curl_setopt($curl, CURLOPT_POSTFIELDS, json_encode($data));
    curl_setopt($curl, CURLOPT_HTTPHEADER, [
        'Content-Type: application/json',
        'Authorization: Basic ' . base64_encode('username:password')
    ]);
    curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);

    $response = curl_exec($curl);
    curl_close($curl);

    return json_decode($response, true);
}

// Função para monitorar atividades
function monitorActivity() {
    global $PHP_AGENT_URL;

    $response = file_get_contents($PHP_AGENT_URL . '/search?jql=project=' . PHP_AGENT_PROJECT_ID . '&fields=id,status');
    $issues = json_decode($response, true);

    foreach ($issues['issues'] as $issue) {
        echo "Issue ID: {$issue['id']} - Status: {$issue['fields']['status']['name']}\n";
    }
}

// Função principal
function main() {
    try {
        // Criar um novo issue
        $newIssue = createIssue('Teste Issue', 'Descrição do teste');
        echo "Novo issue criado com ID: {$newIssue['id']}\n";

        // Monitorar atividades
        monitorActivity();
    } catch (Exception $e) {
        echo "Erro: " . $e->getMessage() . "\n";
    }
}

// Executar a função principal
if (__name__ == "__main__") {
    main();
}