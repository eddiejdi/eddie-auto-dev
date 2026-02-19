<?php

// Configuração do Jira API
$jiraUrl = 'https://your-jira-instance.com';
$jiraUsername = 'your-username';
$jiraPassword = 'your-password';

// Função para realizar a autenticação com o Jira API
function authenticate($jiraUrl, $jiraUsername, $jiraPassword) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $jiraUrl . '/rest/api/2/session');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query([
        'username' => $jiraUsername,
        'password' => $jiraPassword
    ]));
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Content-Type: application/x-www-form-urlencoded'
    ]);

    $response = curl_exec($ch);
    curl_close($ch);

    return json_decode($response, true);
}

// Função para criar uma nova tarefa no Jira
function createTask($jiraUrl, $sessionToken, $projectKey, $summary) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $jiraUrl . '/rest/api/2/issue');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query([
        'fields' => json_encode([
            'project' => [
                'key' => $projectKey
            ],
            'summary' => $summary,
            'description' => 'Task created via PHP Agent',
            'issuetype' => [
                'name' => 'Bug'
            ]
        ])
    ]));
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Content-Type: application/json',
        'Authorization: Bearer ' . $sessionToken
    ]);

    $response = curl_exec($ch);
    curl_close($ch);

    return json_decode($response, true);
}

// Função para listar todas as tarefas do projeto no Jira
function listTasks($jiraUrl, $sessionToken, $projectKey) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $jiraUrl . '/rest/api/2/search?jql=project=' . $projectKey);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Content-Type: application/json',
        'Authorization: Bearer ' . $sessionToken
    ]);

    $response = curl_exec($ch);
    curl_close($ch);

    return json_decode($response, true);
}

// Função principal para executar o script
function main() {
    // Autenticação com o Jira API
    $sessionToken = authenticate($jiraUrl, $jiraUsername, $jiraPassword);

    // Criar uma nova tarefa no Jira
    createTask($jiraUrl, $sessionToken, 'YOUR-PROJECT-KEY', 'Test Task');

    // Listar todas as tarefas do projeto no Jira
    $tasks = listTasks($jiraUrl, $sessionToken, 'YOUR-PROJECT-KEY');
    print_r($tasks);
}

// Executa a função main()
if (__name__ == "__main__") {
    main();
}