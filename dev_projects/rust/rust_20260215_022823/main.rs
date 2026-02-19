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
    let username = "your-username";
    let password = "your-password";

    let issue_data = JiraIssue {
        key: String::from("TEST-123"),
        summary: String::from("Sample Test Case"),
        status: String::from("In Progress"),
    };

    let headers = [("Content-Type", "application/json"), ("Authorization", format!("Basic {}", base64::encode(&format!("{}:{}", username, password))))];

    let response = reqwest::Client::new()
        .post(jira_url)
        .headers(headers)
        .json(&issue_data)
        .send()?;

    if response.status().is_success() {
        println!("Issue created successfully!");
    } else {
        eprintln!("Failed to create issue: {}", response.text()?);
    }

    Ok(())
}