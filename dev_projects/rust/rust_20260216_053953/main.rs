use reqwest;
use serde_json::Value;

// Define a struct to represent the Jira issue
#[derive(Debug)]
struct Issue {
    key: String,
    summary: String,
    status: String,
}

// Function to fetch an issue from Jira
async fn get_issue(issue_key: &str) -> Result<Issue, reqwest::Error> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
    let response = reqwest::get(&url).await?;
    if response.status().is_success() {
        Ok(response.json::<Issue>().await?)
    } else {
        Err(reqwest::Error::from(response))
    }
}

// Function to monitor an issue and report its status
async fn monitor_issue(issue_key: &str) -> Result<(), reqwest::Error> {
    let mut last_status = String::new();
    loop {
        let issue = get_issue(issue_key).await?;
        if issue.status != last_status {
            println!("Issue {} has changed status to {}", issue.key, issue.status);
            last_status = issue.status.clone();
        }
        tokio::time::sleep(tokio::time::Duration::from_secs(60)).await;
    }
}

// Main function
#[tokio::main]
async fn main() -> Result<(), reqwest::Error> {
    let issue_key = "RUST-12";
    monitor_issue(issue_key).await?;
    Ok(())
}