use reqwest;
use serde_json;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn fetch_issue(issue_key: &str) -> Result<JiraIssue, reqwest::Error> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
    let response = reqwest::get(&url).await?;
    if response.status().is_success() {
        Ok(serde_json::from_str::<JiraIssue>(&response.text().await?)?)
    } else {
        Err(reqwest::Error::new(reqwest::StatusCode::INTERNAL_SERVER_ERROR, "Failed to fetch issue"))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let issue_key = "RUST-12";
    let issue = fetch_issue(issue_key).await?;

    println!("Issue Key: {}", issue.key);
    println!("Summary: {}", issue.summary);
    println!("Status: {}", issue.status);

    Ok(())
}