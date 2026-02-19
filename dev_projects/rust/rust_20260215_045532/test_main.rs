use reqwest;
use serde_json::Value;
use std::{env, fs};

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn fetch_jira_issue(issue_key: &str) -> Result<JiraIssue, Box<dyn std::error::Error>> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
    let response = reqwest::get(&url).await?;
    if response.status().is_success() {
        let json: Value = serde_json::from_str(&response.text().await)?;
        Ok(JiraIssue {
            key: json["key"].as_str()?.to_string(),
            summary: json["fields"]["summary"].as_str()?.to_string(),
            status: json["fields"]["status"]["name"].as_str()?.to_string(),
        })
    } else {
        Err(format!("Failed to fetch issue: {}", response.status()).into())
    }
}

async fn log_to_file(issue: &JiraIssue) -> Result<(), Box<dyn std::error::Error>> {
    let file_path = "jira.log";
    fs::append(file_path, format!("Key: {}, Summary: {}, Status: {}\n", issue.key, issue.summary, issue.status)).await?;
    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_instance = env::var("JIRA_INSTANCE").expect("JIRA_INSTANCE environment variable must be set");
    let issue_key = env::var("ISSUE_KEY").expect("ISSUE_KEY environment variable must be set");

    let mut issues: Vec<JiraIssue> = vec![];

    for _ in 0..12 {
        let issue = fetch_jira_issue(&issue_key).await?;
        issues.push(issue);
        log_to_file(&issue).await?;
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_fetch_jira_issue_success() {
        let issue_key = "ABC-123";
        let response = fetch_jira_issue(issue_key).await;
        assert!(response.is_ok());
        let issue = response.unwrap();
        assert_eq!(issue.key, "ABC-123");
    }

    #[tokio::test]
    async fn test_fetch_jira_issue_failure() {
        let issue_key = "NON_EXISTENT";
        let response = fetch_jira_issue(issue_key).await;
        assert!(response.is_err());
    }

    #[tokio::test]
    async fn test_log_to_file_success() {
        let issue = JiraIssue {
            key: "ABC-123".to_string(),
            summary: "Test Issue".to_string(),
            status: "Open".to_string(),
        };
        log_to_file(&issue).await;
    }

    #[tokio::test]
    async fn test_log_to_file_failure() {
        let issue = JiraIssue {
            key: "ABC-123".to_string(),
            summary: "".to_string(),
            status: "".to_string(),
        };
        log_to_file(&issue).await;
    }
}