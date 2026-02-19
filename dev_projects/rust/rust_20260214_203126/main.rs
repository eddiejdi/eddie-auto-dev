use std::io::{self, Write};
use reqwest;
use serde_json;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

impl JiraIssue {
    fn new(key: &str, summary: &str, status: &str) -> Self {
        JiraIssue {
            key: key.to_string(),
            summary: summary.to_string(),
            status: status.to_string(),
        }
    }

    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "key": self.key,
            "summary": self.summary,
            "status": self.status
        })
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_key = "ABC-123";
    let jira_summary = "Fix bug in login page";
    let jira_status = "In Progress";

    let issue = JiraIssue::new(jira_key, jira_summary, jira_status);

    let json_data = issue.to_json();

    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", jira_key);
    let response = reqwest::Client::new()
        .post(url)
        .json(&json_data)
        .send()?;

    if response.status().is_success() {
        println!("Issue created successfully!");
    } else {
        eprintln!("Failed to create issue: {}", response.text()?);
    }

    Ok(())
}