<?php

// Configuração do PHP Agent
define('PHP_AGENT_URL', 'http://localhost:8080');
define('PHP_AGENT_KEY', 'your_agent_key');

// Função para enviar dados ao PHP Agent
function sendToAgent($data) {
    $url = PHP_AGENT_URL . '/track';
    $headers = [
        'Content-Type' => 'application/json',
        'Authorization' => 'Bearer ' . PHP_AGENT_KEY,
    ];

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_POST, 1);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

    $response = curl_exec($ch);
    curl_close($ch);

    return $response;
}

// Função para criar um novo item de tarefa
function createTask($projectKey, $summary, $description) {
    $data = [
        'projectKey' => $projectKey,
        'summary' => $summary,
        'description' => $description,
    ];

    return sendToAgent($data);
}

// Função para atualizar um item de tarefa
function updateTask($taskId, $summary, $description) {
    $data = [
        'taskId' => $taskId,
        'summary' => $summary,
        'description' => $description,
    ];

    return sendToAgent($data);
}

// Função para deletar um item de tarefa
function deleteTask($taskId) {
    $data = [
        'taskId' => $taskId,
    ];

    return sendToAgent($data);
}

// Função principal do programa
function main() {
    // Criar uma nova tarefa
    $projectKey = 'YOUR_PROJECT_KEY';
    $summary = 'New Task';
    $description = 'This is a new task created by the PHP Agent.';
    $task = createTask($projectKey, $summary, $description);
    echo "Created Task: " . json_encode($task) . "\n";

    // Atualizar uma tarefa
    $taskId = 'YOUR_TASK_ID';
    $updatedSummary = 'Updated Task Summary';
    $updatedDescription = 'This task has been updated by the PHP Agent.';
    $updatedTask = updateTask($taskId, $updatedSummary, $updatedDescription);
    echo "Updated Task: " . json_encode($updatedTask) . "\n";

    // Deletar uma tarefa
    $deleteTaskId = 'YOUR_TASK_ID';
    $deleteResponse = deleteTask($deleteTaskId);
    if ($deleteResponse === 'Task deleted successfully') {
        echo "Deleted Task: " . $deleteResponse . "\n";
    } else {
        echo "Failed to delete task: " . $deleteResponse . "\n";
    }
}

// Executar o programa
if (__name__ == "__main__") {
    main();
}