<?php

// Configuração do Jira API
define('JIRA_URL', 'https://your-jira-instance.atlassian.net/rest/api/3');
define('JIRA_USERNAME', 'your-username');
define('JIRA_PASSWORD', 'your-password');

// Função para autenticar na API do Jira
function authenticate($url, $username, $password) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url . '/session/authenticate');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query([
        'username' => $username,
        'password' => $password
    ]));
    $response = curl_exec($ch);
    curl_close($ch);

    return json_decode($response, true);
}

// Função para criar uma nova atividade no Jira
function createIssue($url, $projectKey, $summary, $description) {
    $headers = [
        'Content-Type: application/json'
    ];

    $data = [
        'fields' => [
            'project' => ['key' => $projectKey],
            'summary' => $summary,
            'description' => $description
        ]
    ];

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url . '/issue');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    $response = curl_exec($ch);
    curl_close($ch);

    return json_decode($response, true);
}

// Função para atualizar uma atividade no Jira
function updateIssue($url, $issueKey, $summary, $description) {
    $headers = [
        'Content-Type: application/json'
    ];

    $data = [
        'fields' => [
            'summary' => $summary,
            'description' => $description
        ]
    ];

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url . '/issue/' . $issueKey);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    $response = curl_exec($ch);
    curl_close($ch);

    return json_decode($response, true);
}

// Função para deletar uma atividade no Jira
function deleteIssue($url, $issueKey) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url . '/issue/' . $issueKey);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'DELETE');
    $response = curl_exec($ch);
    curl_close($ch);

    return json_decode($response, true);
}

// Função para listar todas as atividades do Jira
function listIssues($url) {
    $headers = [
        'Content-Type: application/json'
    ];

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url . '/issue');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    $response = curl_exec($ch);
    curl_close($ch);

    return json_decode($response, true);
}

// Função para executar a tarefa de scrum-15
function executeScrum15() {
    // Autenticar na API do Jira
    $session = authenticate(JIRA_URL, JIRA_USERNAME, JIRA_PASSWORD);

    // Criar uma nova atividade no Jira
    $issueKey = createIssue(JIRA_URL, 'YOUR-PROJECT', 'Task 1', 'This is the first task for the project.');

    // Atualizar a atividade no Jira
    updateIssue(JIRA_URL, $issueKey, 'Task 1', 'This is the updated task for the project.');

    // Deletar a atividade do Jira
    deleteIssue(JIRA_URL, $issueKey);

    // Listar todas as atividades do Jira
    $issues = listIssues(JIRA_URL);
    print_r($issues);
}

// Ponto de entrada do programa
if (__name__ == "__main__") {
    executeScrum15();
}