use std::io::{self, Write};
use reqwest;
use serde_json;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut client = reqwest::Client::new();

    // Simulação de dados fictícios
    let issue_data = serde_json::json!({
        "key": "JIRA-123",
        "summary": "Rust Agent Integration with Jira",
        "status": "In Progress"
    });

    // Enviar o dado para Jira usando a API REST do Jira
    let response = client.post("https://your-jira-instance.atlassian.net/rest/api/2/issue")
        .json(&issue_data)
        .send()?;

    if response.status().is_success() {
        println!("Issue created successfully!");
    } else {
        eprintln!("Failed to create issue: {}", response.text()?);
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_issue_success() {
        let mut client = reqwest::Client::new();

        // Simulação de dados fictícios
        let issue_data = serde_json::json!({
            "key": "JIRA-123",
            "summary": "Rust Agent Integration with Jira",
            "status": "In Progress"
        });

        // Enviar o dado para Jira usando a API REST do Jira
        let response = client.post("https://your-jira-instance.atlassian.net/rest/api/2/issue")
            .json(&issue_data)
            .send()?;

        assert!(response.status().is_success());
    }

    #[test]
    fn test_create_issue_failure() {
        let mut client = reqwest::Client::new();

        // Simulação de dados fictícios
        let issue_data = serde_json::json!({
            "key": "JIRA-123",
            "summary": "Rust Agent Integration with Jira",
            "status": ""
        });

        // Enviar o dado para Jira usando a API REST do Jira
        let response = client.post("https://your-jira-instance.atlassian.net/rest/api/2/issue")
            .json(&issue_data)
            .send()?;

        assert!(!response.status().is_success());
    }
}