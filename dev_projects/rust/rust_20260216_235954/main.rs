use reqwest::Client;
use serde_json::json;

// Definição da classe para representar uma tarefa no Jira
struct Task {
    id: String,
    summary: String,
    status: String,
}

// Implementação da função para conectar ao servidor Jira e enviar dados sobre tarefas
async fn send_task_to_jira(task: &Task, jira_url: &str) -> Result<(), reqwest::Error> {
    let client = Client::new();
    let json_data = json!({
        "fields": {
            "summary": task.summary,
            "status": task.status,
        }
    });

    client.post(format!("{}rest/api/2/issue", jira_url))
         .json(&json_data)
         .send()
         .await?;

    Ok(())
}

// Função principal para executar o agent
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Definição das tarefas a serem enviadas ao Jira
    let tasks = vec![
        Task {
            id: "12345".to_string(),
            summary: "Implementar o agent em Rust",
            status: "In Progress",
        },
        Task {
            id: "67890".to_string(),
            summary: "Conectar ao servidor Jira",
            status: "In Progress",
        },
    ];

    // URL do servidor Jira
    let jira_url = "https://your-jira-server.atlassian.net/";

    // Conecte-se ao servidor Jira e envie as tarefas
    for task in tasks {
        send_task_to_jira(&task, &jira_url).await?;
    }

    println!("Tarefas enviadas com sucesso!");

    Ok(())
}