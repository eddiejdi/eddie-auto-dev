use reqwest::Error;
use serde_json::{json, Value};
use crate::Task;

#[tokio::test]
async fn send_task_to_jira_success() {
    let task = Task {
        id: "12345".to_string(),
        summary: "Implementar o agent em Rust",
        status: "In Progress",
    };

    let jira_url = "https://your-jira-server.atlassian.net/";

    match send_task_to_jira(&task, &jira_url).await {
        Ok(_) => assert!(true), // Caso de sucesso
        Err(e) => panic!("Erro ao enviar tarefa: {}", e),
    }
}

#[tokio::test]
async fn send_task_to_jira_error() {
    let task = Task {
        id: "12345".to_string(),
        summary: "Implementar o agent em Rust",
        status: "In Progress",
    };

    let jira_url = "https://your-jira-server.atlassian.net/";

    match send_task_to_jira(&task, &jira_url).await {
        Ok(_) => panic!("Erro esperado ao enviar tarefa"),
        Err(e) => assert!(e.is_reqwest()), // Caso de erro
    }
}