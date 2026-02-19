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
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let auth_token = "your-auth-token";

    // Create a new JiraIssue
    let issue = JiraIssue {
        key: "ABC-123".to_string(),
        summary: "Test Issue".to_string(),
        status: "Open".to_string(),
    };

    // Serialize the issue to JSON
    let json_data = serde_json::to_string(&issue)?;

    // Create a new HTTP client and send a POST request to create the issue
    let client = reqwest::Client::new();
    let response = client.post(jira_url)
        .header("Authorization", format!("Basic {}", auth_token))
        .header("Content-Type", "application/json")
        .body(json_data)
        .send()?;

    // Check if the request was successful
    if response.status().is_success() {
        println!("Issue created successfully!");
    } else {
        eprintln!("Failed to create issue: {:?}", response.text());
    }

    Ok(())
}

// Teste para criar um novo issue com valores válidos
#[test]
fn test_create_issue_valid_values() {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let auth_token = "your-auth-token";

    // Create a new JiraIssue
    let issue = JiraIssue {
        key: "ABC-123".to_string(),
        summary: "Test Issue".to_string(),
        status: "Open".to_string(),
    };

    // Serialize the issue to JSON
    let json_data = serde_json::to_string(&issue)?;

    // Create a new HTTP client and send a POST request to create the issue
    let client = reqwest::Client::new();
    let response = client.post(jira_url)
        .header("Authorization", format!("Basic {}", auth_token))
        .header("Content-Type", "application/json")
        .body(json_data)
        .send()?;

    // Check if the request was successful
    assert!(response.status().is_success());
}

// Teste para criar um novo issue com valores inválidos (divisão por zero)
#[test]
fn test_create_issue_invalid_values_division_by_zero() {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let auth_token = "your-auth-token";

    // Create a new JiraIssue with an invalid value
    let issue = JiraIssue {
        key: "ABC-123".to_string(),
        summary: "Test Issue".to_string(),
        status: "Open".to_string(),
    };

    // Serialize the issue to JSON
    let json_data = serde_json::to_string(&issue)?;

    // Create a new HTTP client and send a POST request to create the issue
    let client = reqwest::Client::new();
    let response = client.post(jira_url)
        .header("Authorization", format!("Basic {}", auth_token))
        .header("Content-Type", "application/json")
        .body(json_data)
        .send()?;

    // Check if the request was successful
    assert!(response.status().is_success());
}

// Teste para criar um novo issue com valores inválidos (valores vazios)
#[test]
fn test_create_issue_invalid_values_empty_strings() {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let auth_token = "your-auth-token";

    // Create a new JiraIssue with empty strings
    let issue = JiraIssue {
        key: "".to_string(),
        summary: "".to_string(),
        status: "".to_string(),
    };

    // Serialize the issue to JSON
    let json_data = serde_json::to_string(&issue)?;

    // Create a new HTTP client and send a POST request to create the issue
    let client = reqwest::Client::new();
    let response = client.post(jira_url)
        .header("Authorization", format!("Basic {}", auth_token))
        .header("Content-Type", "application/json")
        .body(json_data)
        .send()?;

    // Check if the request was successful
    assert!(response.status().is_success());
}

// Teste para criar um novo issue com valores inválidos (None)
#[test]
fn test_create_issue_invalid_values_none() {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let auth_token = "your-auth-token";

    // Create a new JiraIssue with None values
    let issue = JiraIssue {
        key: None,
        summary: None,
        status: None,
    };

    // Serialize the issue to JSON
    let json_data = serde_json::to_string(&issue)?;

    // Create a new HTTP client and send a POST request to create the issue
    let client = reqwest::Client::new();
    let response = client.post(jira_url)
        .header("Authorization", format!("Basic {}", auth_token))
        .header("Content-Type", "application/json")
        .body(json_data)
        .send()?;

    // Check if the request was successful
    assert!(response.status().is_success());
}