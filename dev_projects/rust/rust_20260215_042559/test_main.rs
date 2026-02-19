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
    // Configuração do Rust Agent
    let agent_config = "your_agent_config_here";

    // Conecte-se ao Jira API
    let client = reqwest::Client::new();

    // Define a função para buscar issues no Jira
    async fn fetch_issues(client: &reqwest::Client, jql: String) -> Result<Vec<JiraIssue>, Box<dyn std::error::Error>> {
        let response = client.get("https://your-jira-instance.atlassian.net/rest/api/2/search")
            .query(&[("jql", jql)])
            .send()
            .await?;

        if response.status().is_success() {
            let issues: Vec<JiraIssue> = serde_json::from_str(&response.text().await?)?;
            Ok(issues)
        } else {
            Err(format!("Failed to fetch issues: {}", response.status()).into())
        }
    }

    // Define a função para processar e exibir as issues
    async fn process_issues(client: &reqwest::Client, issues: Vec<JiraIssue>) -> Result<(), Box<dyn std::error::Error>> {
        for issue in issues {
            println!("Key: {}, Summary: {}, Status: {}", issue.key, issue.summary, issue.status);
        }
        Ok(())
    }

    // Exemplo de uso
    let jql = "project = YourProject AND status = In Progress";
    let issues = fetch_issues(&client, jql).await?;
    process_issues(&client, issues).await?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_fetch_issues_success() {
        let client = reqwest::Client::new();
        let jql = "project = YourProject AND status = In Progress";
        let issues = fetch_issues(&client, jql).await.unwrap();

        assert_eq!(issues.len(), 1);
        assert_eq!(issues[0].key, "ABC-123");
    }

    #[tokio::test]
    async fn test_fetch_issues_failure() {
        let client = reqwest::Client::new();
        let jql = "project = YourProject AND status = Invalid";
        let result = fetch_issues(&client, jql).await;

        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_process_issues_success() {
        let client = reqwest::Client::new();
        let issues = vec![JiraIssue {
            key: "ABC-123".to_string(),
            summary: "Fix bug in the application".to_string(),
            status: "In Progress".to_string(),
        }];
        process_issues(&client, issues).await.unwrap();

        assert_eq!(issues[0].status, "Done");
    }

    #[tokio::test]
    async fn test_process_issues_failure() {
        let client = reqwest::Client::new();
        let issues = vec![JiraIssue {
            key: "ABC-123".to_string(),
            summary: "Fix bug in the application".to_string(),
            status: "Done".to_string(), // This should fail
        }];
        let result = process_issues(&client, issues).await;

        assert!(result.is_err());
    }
}