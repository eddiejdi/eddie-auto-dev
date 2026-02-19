// Importações necessárias
use reqwest;
use serde_json;
use std::error::Error;

// Definição da struct Jira
#[derive(Debug)]
struct Jira {
    url: String,
    token: String,
}

impl Jira {
    fn new(url: &str, token: &str) -> Self {
        Jira {
            url: url.to_string(),
            token: token.to_string(),
        }
    }

    async fn send_activity(&self, activity: &Activity) -> Result<(), Box<dyn Error>> {
        let headers = reqwest::HeaderMap::from([
            ("Authorization".to_string(), format!("Bearer {}", self.token)),
            ("Content-Type".to_string(), "application/json".to_string()),
        ]);

        let response = reqwest::post(&self.url)
            .headers(headers)
            .json(activity)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(format!("Failed to send activity: {}", response.text().await?).into())
        }
    }
}

// Definição da struct Activity
#[derive(Debug)]
struct Activity {
    project_id: String,
    issue_key: String,
    status: String,
    comment: String,
}

impl Activity {
    fn new(project_id: &str, issue_key: &str, status: &str, comment: &str) -> Self {
        Activity {
            project_id: project_id.to_string(),
            issue_key: issue_key.to_string(),
            status: status.to_string(),
            comment: comment.to_string(),
        }
    }
}

// Função main para executar o programa
#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    // Configurações do Jira
    let jira = Jira::new("https://your-jira-instance.atlassian.net/rest/api/3", "your-api-token");

    // Criação de uma atividade
    let activity = Activity::new(
        "10100", // ID do projeto
        "ABC-123", // ID da tarefa
        "In Progress", // Status atual
        "This is a test comment.", // Comentário
    );

    // Envia a atividade para Jira
    jira.send_activity(&activity).await?;

    println!("Activity sent successfully!");

    Ok(())
}