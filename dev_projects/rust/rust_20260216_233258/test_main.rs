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

    // Simula um usuário logado em Jira
    let username = "your_username";
    let password = "your_password";

    // Cria o payload para autenticação
    let auth_payload = serde_json::json!({
        "username": username,
        "password": password
    });

    // Faz a requisição de autenticação
    let response = client.post("https://your-jira-instance.atlassian.net/rest/api/2/session")
        .header("Content-Type", "application/json")
        .body(auth_payload.to_string())
        .send()?;

    if !response.status().is_success() {
        return Err(format!("Failed to authenticate: {}", response.text()).into());
    }

    // Simula um issue existente em Jira
    let issue_key = "ABC-123";

    // Cria o payload para obter informações do issue
    let issue_payload = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": "Test Issue",
            "description": "This is a test issue created by Rust Agent"
        }
    });

    // Faz a requisição para obter informações do issue
    let response = client.post(&format!("https://your-jira-instance.atlassian.net/rest/api/2/issue"))
        .header("Content-Type", "application/json")
        .header("Authorization", format!("Bearer {}", response.text()?))
        .body(issue_payload.to_string())
        .send()?;

    if !response.status().is_success() {
        return Err(format!("Failed to create issue: {}", response.text()).into());
    }

    println!("Issue created successfully!");

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_authenticate_with_valid_credentials() {
        let mut client = reqwest::Client::new();

        // Simula um usuário logado em Jira
        let username = "your_username";
        let password = "your_password";

        // Cria o payload para autenticação
        let auth_payload = serde_json::json!({
            "username": username,
            "password": password
        });

        // Faz a requisição de autenticação
        let response = client.post("https://your-jira-instance.atlassian.net/rest/api/2/session")
            .header("Content-Type", "application/json")
            .body(auth_payload.to_string())
            .send()?;

        assert!(response.status().is_success());
    }

    #[test]
    fn test_authenticate_with_invalid_credentials() {
        let mut client = reqwest::Client::new();

        // Simula um usuário logado em Jira
        let username = "your_username";
        let password = "invalid_password";

        // Cria o payload para autenticação
        let auth_payload = serde_json::json!({
            "username": username,
            "password": password
        });

        // Faz a requisição de autenticação
        let response = client.post("https://your-jira-instance.atlassian.net/rest/api/2/session")
            .header("Content-Type", "application/json")
            .body(auth_payload.to_string())
            .send()?;

        assert!(!response.status().is_success());
    }

    #[test]
    fn test_create_issue_with_valid_data() {
        let mut client = reqwest::Client::new();

        // Simula um usuário logado em Jira
        let username = "your_username";
        let password = "your_password";

        // Cria o payload para autenticação
        let auth_payload = serde_json::json!({
            "username": username,
            "password": password
        });

        // Faz a requisição de autenticação
        let response = client.post("https://your-jira-instance.atlassian.net/rest/api/2/session")
            .header("Content-Type", "application/json")
            .body(auth_payload.to_string())
            .send()?;

        assert!(response.status().is_success());

        // Simula um issue existente em Jira
        let issue_key = "ABC-123";

        // Cria o payload para obter informações do issue
        let issue_payload = serde_json::json!({
            "fields": {
                "project": {"key": "YOUR_PROJECT_KEY"},
                "summary": "Test Issue",
                "description": "This is a test issue created by Rust Agent"
            }
        });

        // Faz a requisição para obter informações do issue
        let response = client.post(&format!("https://your-jira-instance.atlassian.net/rest/api/2/issue"))
            .header("Content-Type", "application/json")
            .header("Authorization", format!("Bearer {}", response.text()?))
            .body(issue_payload.to_string())
            .send()?;

        assert!(response.status().is_success());
    }

    #[test]
    fn test_create_issue_with_invalid_data() {
        let mut client = reqwest::Client::new();

        // Simula um usuário logado em Jira
        let username = "your_username";
        let password = "your_password";

        // Cria o payload para autenticação
        let auth_payload = serde_json::json!({
            "username": username,
            "password": password
        });

        // Faz a requisição de autenticação
        let response = client.post("https://your-jira-instance.atlassian.net/rest/api/2/session")
            .header("Content-Type", "application/json")
            .body(auth_payload.to_string())
            .send()?;

        assert!(response.status().is_success());

        // Simula um issue existente em Jira
        let issue_key = "ABC-123";

        // Cria o payload para obter informações do issue com dados inválidos
        let invalid_issue_payload = serde_json::json!({
            "fields": {
                "project": {"key": "YOUR_PROJECT_KEY"},
                "summary": "Test Issue",
                "description": ""
            }
        });

        // Faz a requisição para obter informações do issue com dados inválidos
        let response = client.post(&format!("https://your-jira-instance.atlassian.net/rest/api/2/issue"))
            .header("Content-Type", "application/json")
            .header("Authorization", format!("Bearer {}", response.text()?))
            .body(invalid_issue_payload.to_string())
            .send()?;

        assert!(!response.status().is_success());
    }
}