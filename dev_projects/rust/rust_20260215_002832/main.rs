use reqwest;
use serde::{Deserialize, Serialize};
use std::error::Error;

#[derive(Serialize, Deserialize)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn fetch_issue(jira_url: &str, issue_key: &str) -> Result<JiraIssue, Box<dyn Error>> {
    let response = reqwest::get(format!("{}rest/api/2/issue/{}", jira_url, issue_key))
        .await?;
    
    if response.status().is_success() {
        Ok(response.json::<JiraIssue>().await?)
    } else {
        Err(Box::new(response.text().await.unwrap_or("Failed to fetch issue".to_string()).into()))
    }
}

#[derive(Serialize, Deserialize)]
struct JiraAgentConfig {
    jira_url: String,
    issue_key: String,
}

fn main() -> Result<(), Box<dyn Error>> {
    let config = JiraAgentConfig {
        jira_url: "https://your-jira-instance.atlassian.net".to_string(),
        issue_key: "ABC-123".to_string(),
    };

    match fetch_issue(&config.jira_url, &config.issue_key) {
        Ok(issue) => println!("Issue: {}", issue.summary),
        Err(e) => eprintln!("Error fetching issue: {}", e),
    }

    Ok(())
}