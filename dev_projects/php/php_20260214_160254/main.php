<?php

// Configuração do PHP Agent
define('PHP_AGENT_URL', 'http://localhost:8080');
define('PHP_AGENT_KEY', 'your_agent_key');

// Configuração da API Jira
define('JIRA_API_URL', 'https://your_jira_instance.atlassian.net/rest/api/3');
define('JIRA_API_TOKEN', 'your_api_token');

// Classe para manipulação de tarefas no Jira
class TaskManager {
    public function createTask($projectKey, $summary, $description) {
        $data = [
            'fields' => [
                'project' => ['key' => $projectKey],
                'summary' => $summary,
                'description' => $description,
                'issuetype' => ['name' => 'Bug']
            ]
        ];

        $response = curl_post(JIRA_API_URL . '/issue', JSON_ENCODE($data), JIRA_API_TOKEN);
        return json_decode($response, true);
    }

    public function updateTask($issueKey, $summary, $description) {
        $data = [
            'fields' => [
                'summary' => $summary,
                'description' => $description
            ]
        ];

        $response = curl_put(JIRA_API_URL . '/issue/' . $issueKey, JSON_ENCODE($data), JIRA_API_TOKEN);
        return json_decode($response, true);
    }

    public function deleteTask($issueKey) {
        $response = curl_delete(JIRA_API_URL . '/issue/' . $issueKey, JIRA_API_TOKEN);
        return json_decode($response, true);
    }
}

// Função principal
function main() {
    // Cria uma instância do TaskManager
    $taskManager = new TaskManager();

    // Criar uma nova tarefa
    $newTask = $taskManager->createTask('YOUR_PROJECT_KEY', 'Implement PHP Agent with Jira', 'Track tasks using PHP Agent and Jira API');
    echo "New task created: " . json_encode($newTask) . "\n";

    // Atualizar a tarefa
    $updatedTask = $taskManager->updateTask($newTask['key'], 'Implement PHP Agent with Jira', 'Update task details using PHP Agent and Jira API');
    echo "Updated task: " . json_encode($updatedTask) . "\n";

    // Excluir a tarefa
    $deletedTask = $taskManager->deleteTask($newTask['key']);
    echo "Deleted task: " . json_encode($deletedTask) . "\n";
}

// Executa o programa se for chamado como um script
if (__name__ == "__main__") {
    main();
}