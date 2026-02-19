use std::io::{self, Write};
use reqwest;
use serde_json;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

fn fetch_issue(jira_key: &str) -> Result<JiraIssue, Box<dyn std::error::Error>> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", jira_key);
    let response = reqwest::get(&url)?;

    if !response.status().is_success() {
        return Err(format!("Failed to fetch issue: {}", response.status()).into());
    }

    let json_response = response.text()?;
    serde_json::from_str::<JiraIssue>(&json_response).map_err(|e| e.into())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Teste de sucesso com valores válidos
    assert_eq!(
        fetch_issue("ABC-123").unwrap(),
        JiraIssue {
            key: "ABC-123".to_string(),
            summary: "Test issue".to_string(),
            status: "Open".to_string(),
        }
    );

    // Teste de erro (divisão por zero)
    assert_eq!(
        fetch_issue("XYZ-456").unwrap_err().to_string(),
        "Failed to fetch issue: 0.0 / 0.0"
    );

    // Teste de erro (valores inválidos)
    assert_eq!(
        fetch_issue("ABC!123").unwrap_err().to_string(),
        "Failed to fetch issue: Invalid JSON format"
    );

    println!("All tests passed!");
    Ok(())
}