use reqwest;
use serde_json::Value;

// Define a struct to represent a Jira issue
#[derive(Debug)]
struct Issue {
    key: String,
    summary: String,
    status: String,
}

// Function to fetch issues from Jira API
async fn fetch_issues(url: &str, token: &str) -> Result<Vec<Issue>, reqwest::Error> {
    let response = reqwest::get(url)
        .header("Authorization", format!("Bearer {}", token))
        .send()
        .await?;

    if !response.status().is_success() {
        return Err(reqwest::Error::from(response));
    }

    let text = response.text().await?;
    serde_json::from_str(&text).map_err(|e| e.into())
}

// Function to monitor real-time issues
async fn monitor_issues(url: &str, token: &str) -> Result<(), reqwest::Error> {
    loop {
        let issues = fetch_issues(url, token).await?;

        for issue in issues {
            println!("Issue {}: {}", issue.key, issue.summary);
        }

        tokio::time::sleep(Duration::from_secs(10)).await;
    }
}

// Main function to run the application
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let url = "https://your-jira-instance.atlassian.net/rest/api/2/search";
    let token = "your-jira-api-token";

    monitor_issues(url, token).await?;

    Ok(())
}