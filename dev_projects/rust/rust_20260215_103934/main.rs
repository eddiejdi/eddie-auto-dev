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
    println!("Enter JIRA key:");
    let mut jira_key = String::new();
    io::stdin().read_line(&mut jira_key)?;

    let issue = fetch_issue(&jira_key.trim())?;

    println!("Issue Key: {}", issue.key);
    println!("Summary: {}", issue.summary);
    println!("Status: {}", issue.status);

    Ok(())
}