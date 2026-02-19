<?php

// Configuração do Jira API
define('JIRA_API_URL', 'https://your-jira-instance.atlassian.net/rest/api/3');
define('JIRA_USERNAME', 'your-username');
define('JIRA_PASSWORD', 'your-password');

// Função para autenticar com o Jira API
function authenticate($url, $username, $password) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, "j_username=$username&j_password=$password");
    $response = json_decode(curl_exec($ch), true);
    curl_close($ch);

    if ($response['status'] == 200) {
        return $response['session'];
    } else {
        throw new Exception('Authentication failed: ' . $response['error']);
    }
}

// Função para criar uma tarefa no Jira
function createTask($url, $session, $projectKey, $summary, $description) {
    $headers = [
        'Content-Type: application/json',
        'Authorization: Basic ' . base64_encode("$session:$JIRA_PASSWORD")
    ];

    $data = [
        "fields" => [
            "project" => ["key" => $projectKey],
            "summary" => $summary,
            "description" => $description
        ]
    ];

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url . "/issue");
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    $response = json_decode(curl_exec($ch), true);
    curl_close($ch);

    if ($response['status'] == 201) {
        return $response['key'];
    } else {
        throw new Exception('Failed to create task: ' . $response['error']);
    }
}

// Função para atualizar uma tarefa no Jira
function updateTask($url, $session, $issueKey, $summary = null, $description = null) {
    $headers = [
        'Content-Type: application/json',
        'Authorization: Basic ' . base64_encode("$session:$JIRA_PASSWORD")
    ];

    $data = [];
    if ($summary !== null) {
        $data['fields']['summary'] = $summary;
    }
    if ($description !== null) {
        $data['fields']['description'] = $description;
    }

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url . "/issue/$issueKey");
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    $response = json_decode(curl_exec($ch), true);
    curl_close($ch);

    if ($response['status'] == 204) {
        return;
    } else {
        throw new Exception('Failed to update task: ' . $response['error']);
    }
}

// Função para obter uma tarefa do Jira
function getTask($url, $session, $issueKey) {
    $headers = [
        'Authorization: Basic ' . base64_encode("$session:$JIRA_PASSWORD")
    ];

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url . "/issue/$issueKey");
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    $response = json_decode(curl_exec($ch), true);
    curl_close($ch);

    if ($response['status'] == 200) {
        return $response;
    } else {
        throw new Exception('Failed to get task: ' . $response['error']);
    }
}

// Função para listar todas as tarefas do Jira
function listTasks($url, $session) {
    $headers = [
        'Authorization: Basic ' . base64_encode("$session:$JIRA_PASSWORD")
    ];

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url . "/issue");
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    $response = json_decode(curl_exec($ch), true);
    curl_close($ch);

    if ($response['status'] == 200) {
        return $response['issues'];
    } else {
        throw new Exception('Failed to list tasks: ' . $response['error']);
    }
}

// Função para excluir uma tarefa do Jira
function deleteTask($url, $session, $issueKey) {
    $headers = [
        'Authorization: Basic ' . base64_encode("$session:$JIRA_PASSWORD")
    ];

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url . "/issue/$issueKey");
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "DELETE");
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    $response = json_decode(curl_exec($ch), true);
    curl_close($ch);

    if ($response['status'] == 204) {
        return;
    } else {
        throw new Exception('Failed to delete task: ' . $response['error']);
    }
}

// Função principal
function main() {
    try {
        // Autenticar com o Jira API
        $session = authenticate(JIRA_API_URL, JIRA_USERNAME, JIRA_PASSWORD);

        // Criar uma tarefa no Jira
        $taskKey = createTask(JIRA_API_URL, $session, 'T123', 'Implement PHP Agent for Laravel and Symfony', 'This task is about integrating PHP Agent with Jira for tracking activities in PHP projects.');

        // Atualizar uma tarefa no Jira
        updateTask(JIRA_API_URL, $session, $taskKey, 'Implement PHP Agent for Laravel and Symfony', 'This task is about integrating PHP Agent with Jira for tracking activities in PHP projects.');

        // Obter uma tarefa do Jira
        $task = getTask(JIRA_API_URL, $session, $taskKey);
        print_r($task);

        // Listar todas as tarefas do Jira
        $tasks = listTasks(JIRA_API_URL, $session);
        print_r($tasks);

        // Excluir uma tarefa do Jira
        deleteTask(JIRA_API_URL, $session, $taskKey);
    } catch (Exception $e) {
        echo 'Error: ' . $e->getMessage();
    }
}

// Executar a função principal se o script for executado como um programa principal
if (__name__ == "__main__") {
    main();
}