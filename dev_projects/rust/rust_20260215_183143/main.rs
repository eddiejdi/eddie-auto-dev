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

    // Create a new JiraIssue object
    let issue = JiraIssue {
        key: "ABC-123".to_string(),
        summary: "Sample Issue".to_string(),
        status: "Open".to_string(),
    };

    // Serialize the JiraIssue object to JSON
    let json_data = serde_json::to_string(&issue)?;

    // Send a POST request to create the issue in Jira
    let response = reqwest::Client::new()
        .post(jira_url)
        .header("Authorization", format!("Basic {}", auth_token))
        .header("Content-Type", "application/json")
        .body(json_data)
        .send()?;

    // Check if the request was successful
    if response.status().is_success() {
        println!("Issue created successfully!");
    } else {
        eprintln!("Failed to create issue: {}", response.text()?);
    }

    Ok(())
}