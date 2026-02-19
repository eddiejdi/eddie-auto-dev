use reqwest::Client;
use serde_json::{self, Value};
use tokio::sync::mpsc;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Configuração do cliente HTTP para Jira
    let client = Client::new();

    // Cria um canal de mensagens para enviar tarefas para o servidor
    let (tx, rx) = mpsc::channel(10);

    // Função para monitorar tarefas e enviar para o servidor
    async fn monitor_issues(client: &Client, tx: mpsc::Sender<JiraIssue>) {
        loop {
            // Simula a obtenção de uma nova tarefa do Jira (substitua isso pela lógica real)
            let response = client.get("https://your-jira-instance.atlassian.net/rest/api/2/issue")
                .send()
                .await?;

            if response.status().is_success() {
                let issue: Value = serde_json::from_str(&response.text().await?)?;
                let jira_issue = JiraIssue {
                    key: issue["key"].as_str().unwrap().to_string(),
                    summary: issue["fields"]["summary"].as_str().unwrap().to_string(),
                    status: issue["fields"]["status"]["name"].as_str().unwrap().to_string(),
                };
                tx.send(jira_issue).await?;
            } else {
                println!("Failed to retrieve issue: {}", response.status());
            }

            tokio::time::sleep(tokio::time::Duration::from_secs(60)).await;
        }
    }

    // Inicia a thread para monitorar tarefas
    let handle = tokio::spawn(monitor_issues(&client, tx));

    // Função principal que recebe e processa as tarefas do servidor
    async fn main_loop(rx: mpsc::Receiver<JiraIssue>) {
        loop {
            if let Some(issue) = rx.recv().await {
                println!("Received issue: {:?}", issue);
                // Aqui você pode adicionar lógica para gerenciar o estado da tarefa no Jira
            }
        }
    }

    // Inicia a thread principal que recebe e processa as tarefas do servidor
    let handle = tokio::spawn(main_loop(rx));

    // Espera até que todas as threads terminem
    handle.await?;

    Ok(())
}