<?php

// Configuração do Jira API
$baseUrl = 'https://your-jira-instance.atlassian.net';
$username = 'your-username';
$password = 'your-password';

// Função para autenticar com o Jira API
function authenticate($baseUrl, $username, $password) {
    $url = "$baseUrl/rest/api/2/session";
    $headers = [
        'Content-Type: application/json',
    ];
    $data = json_encode([
        'username' => $username,
        'password' => $password,
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

// Função para criar uma tarefa no Jira
function createTask($baseUrl, $username, $password, $projectKey, $summary) {
    $url = "$baseUrl/rest/api/2/issue";
    $headers = [
        'Content-Type: application/json',
    ];
    $data = json_encode([
        'fields' => [
            'project' => ['key' => $projectKey],
            'summary' => $summary,
            'description' => 'This is a test task created by PHP Agent.',
            'assignee' => ['name' => 'your-username'],
            'priority' => ['id' => 3], // 1 is lowest, 5 is highest
        ],
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

// Função para monitorar atividades do Jira
function monitorActivities($baseUrl, $username, $password) {
    $url = "$baseUrl/rest/api/2/search";
    $headers = [
        'Content-Type: application/json',
    ];
    $data = json_encode([
        'jql' => 'project = ' . $projectKey,
        'fields' => ['summary', 'status'],
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

// Função principal
function main() {
    // Autenticar com o Jira API
    $session = authenticate($baseUrl, $username, $password);

    if ($session['status'] !== 'success') {
        die("Failed to authenticate with Jira: " . json_encode($session));
    }

    // Criar uma tarefa no Jira
    $task = createTask($baseUrl, $username, $password, 'YOUR-PROJECT-KEY', 'Test Task');

    if ($task['status'] !== 'success') {
        die("Failed to create task: " . json_encode($task));
    }

    // Monitorar atividades do Jira
    $activities = monitorActivities($baseUrl, $username, $password);

    if ($activities['status'] !== 'success') {
        die("Failed to monitor activities: " . json_encode($activities));
    }

    echo "Task created successfully with ID: " . $task['id'];
}

// Executar o programa
if (__name__ == "__main__") {
    main();
}