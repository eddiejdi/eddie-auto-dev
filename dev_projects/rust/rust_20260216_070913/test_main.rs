use reqwest;
use serde_json::Value;
use std::io::{self, Write};

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    description: String,
}

async fn fetch_issue(jira_url: &str, issue_key: &str) -> Result<JiraIssue, reqwest::Error> {
    let response = reqwest::get(format!("{}issues/{}", jira_url, issue_key))
        .await?
        .json::<Value>()
        .await?;

    Ok(JiraIssue {
        key: response["key"].as_str().unwrap().to_string(),
        summary: response["fields"]["summary"].as_str().unwrap().to_string(),
        description: response["fields"]["description"].as_str().unwrap().to_string(),
    })
}

async fn update_issue(jira_url: &str, issue_key: &str, new_description: &str) -> Result<(), reqwest::Error> {
    let payload = serde_json::json!({
        "fields": {
            "description": new_description
        }
    });

    let response = reqwest::put(format!("{}issues/{}", jira_url, issue_key))
        .json(&payload)
        .await?;

    if response.status().is_success() {
        Ok(())
    } else {
        Err(reqwest::Error::from(response.text().await.unwrap()))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2";
    let issue_key = "ABC-123";

    // Fetch the current issue
    let mut issue = fetch_issue(jira_url, &issue_key).await?;

    println!("Current Issue:");
    println!("Key: {}", issue.key);
    println!("Summary: {}", issue.summary);
    println!("Description: {}", issue.description);

    // Update the issue description
    let new_description = "Updated by Rust Agent";
    update_issue(jira_url, &issue_key, &new_description).await?;

    println!("Issue updated successfully.");

    Ok(())
}