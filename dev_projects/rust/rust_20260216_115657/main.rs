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
    let issue_key = "YOUR-ISSUE-KEY";

    // Create a new JiraIssue instance
    let mut issue = JiraIssue {
        key: issue_key.to_string(),
        summary: String::new(),
        status: String::new(),
    };

    // Fetch the issue details from Jira
    let response = reqwest::get(format!("{}{}", jira_url, issue.key))?;
    let json_response: serde_json::Value = response.json()?;

    if let Some(issue_data) = json_response["fields"].as_object().unwrap() {
        issue.summary = issue_data.get("summary").map_or(String::new(), |v| v.as_str().unwrap().to_string());
        issue.status = issue_data.get("status").map_or(String::new(), |v| v.as_str().unwrap().to_string());
    }

    // Print the issue details
    println!("Issue Key: {}", issue.key);
    println!("Summary: {}", issue.summary);
    println!("Status: {}", issue.status);

    Ok(())
}