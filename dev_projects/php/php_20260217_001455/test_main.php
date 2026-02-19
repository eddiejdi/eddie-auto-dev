<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

// Configuração do Jira API
$jiraUrl = 'https://your-jira-instance.atlassian.net';
$jiraUsername = 'your-username';
$jiraPassword = 'your-password';

// Função para realizar a autenticação com o Jira
function authenticate($url, $username, $password) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url . '/rest/api/2/session');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query([
        'username' => $username,
        'password' => $password
    ]));
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Content-Type: application/x-www-form-urlencoded'
    ]);

    $response = curl_exec($ch);
    curl_close($ch);

    return json_decode($response, true);
}

// Função para criar uma tarefa no Jira
function createTask($url, $sessionToken, $projectKey, $summary) {
    $headers = [
        'Content-Type: application/json',
        'Authorization: Bearer ' . $sessionToken
    ];

    $data = json_encode([
        'fields' => [
            'project' => ['key' => $projectKey],
            'summary' => $summary,
            'description' => 'This is a new task created by the PHP agent',
            'issuetype' => ['name' => 'Task']
        ]
    ]);

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url . '/rest/api/2/issue');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

    $response = curl_exec($ch);
    curl_close($ch);

    return json_decode($response, true);
}

// Função para monitorar atividades no Jira
function monitorActivities($url, $sessionToken) {
    $headers = [
        'Content-Type: application/json',
        'Authorization: Bearer ' . $sessionToken
    ];

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url . '/rest/api/2/search?jql=project=' . urlencode('YourProjectKey') . '&fields=id,status');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

    $response = curl_exec($ch);
    curl_close($ch);

    return json_decode($response, true);
}

// Função principal
function main() {
    // Autenticação com o Jira
    try {
        $sessionToken = authenticate($jiraUrl, $jiraUsername, $jiraPassword)['session']['token'];
    } catch (Exception $e) {
        echo 'Error: ' . $e->getMessage();
    }

    // Criar uma tarefa no Jira
    try {
        createTask($jiraUrl, $sessionToken, 'YourProjectKey', 'New task created by the PHP agent');
    } catch (Exception $e) {
        echo 'Error creating task: ' . $e->getMessage();
    }

    // Monitorar atividades no Jira
    try {
        $activities = monitorActivities($jiraUrl, $sessionToken);
    } catch (Exception $e) {
        echo 'Error monitoring activities: ' . $e->getMessage();
    }
}

// Executar a função main()
if (__name__ == "__main__") {
    main();
}