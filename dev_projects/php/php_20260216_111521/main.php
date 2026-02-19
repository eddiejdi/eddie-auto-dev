<?php

// Importar classes necessárias
require_once 'Jira.php';
require_once 'PhpAgent.php';

// Função para integrar PHP Agent com Jira
function integratePhpAgentWithJira($jiraUrl, $username, $password) {
    // Criar uma instância do PhpAgent
    $phpAgent = new PhpAgent();

    // Configurar o PhpAgent com as credenciais de autenticação
    $phpAgent->setUsername($username);
    $phpAgent-> setPassword($password);

    // Criar uma instância do Jira
    $jira = new Jira($jiraUrl);

    // Verificar se a conexão com o Jira foi bem-sucedida
    if ($jira->isConnected()) {
        echo "Conexão com o Jira bem-sucedida!\n";

        // Adicionar uma atividade ao Jira
        $activity = 'Integração PHP Agent com Jira';
        $jira->addActivity($activity);

        // Exibir a atividade adicionada ao Jira
        echo "Atividade adicionada ao Jira: " . $activity . "\n";

    } else {
        echo "Falha na conexão com o Jira!\n";
    }
}

// Verificar se o script foi executado como um programa principal (CLI)
if (__name__ == "__main__") {
    // Exemplo de uso da função
    integratePhpAgentWithJira('https://your-jira-instance.com', 'your-username', 'your-password');
}