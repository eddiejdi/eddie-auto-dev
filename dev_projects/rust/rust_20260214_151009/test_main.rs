use std::io::{self, Write};
use reqwest;
use serde_json;

struct Agent {
    jira_url: String,
    username: String,
    password: String,
}

impl Agent {
    fn new(jira_url: &str, username: &str, password: &str) -> Self {
        Agent {
            jira_url: jira_url.to_string(),
            username: username.to_string(),
            password: password.to_string(),
        }
    }

    async fn configure(&self) -> Result<(), Box<dyn std::error::Error>> {
        println!("Configurando o agente...");
        Ok(())
    }

    async fn integrate_jira(&self) -> Result<(), Box<dyn std::error::Error>> {
        let client = reqwest::Client::new();
        let response = client.post(self.jira_url)
            .basic_auth(&self.username, Some(&self.password))
            .json(&serde_json!({
                "action": "create",
                "issue": {
                    "fields": {
                        "project": {"key": "PROJ"},
                        "summary": "Teste do agente",
                        "description": "Este é um teste do agente para Jira.",
                        "assignee": {"name": "user"}
                    }
                }
            }))
            .send()
            .await?;

        if response.status().is_success() {
            println!("Integração com Jira bem-sucedida!");
        } else {
            let error_message = response.text().await?;
            println!("Erro ao integrar com Jira: {}", error_message);
        }

        Ok(())
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let agent = Agent::new("https://your-jira-instance.atlassian.net/rest/api/3", "username", "password");

    // Configuração do agente
    agent.configure().await?;

    // Integração com Jira
    agent.integrate_jira().await?;

    Ok(())
}