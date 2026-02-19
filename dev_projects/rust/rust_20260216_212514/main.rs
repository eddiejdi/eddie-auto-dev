use reqwest;
use serde_json::Value;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn fetch_issue(jira_url: &str, issue_key: &str) -> Result<JiraIssue, reqwest::Error> {
    let response = reqwest::get(format!("{}rest/api/2/issue/{}", jira_url, issue_key))
        .await?;
    
    if response.status().is_success() {
        Ok(response.json::<JiraIssue>().await?)
    } else {
        Err(reqwest::Error::from(response.text().await?))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net";
    let issue_key = "ABC-123";

    match fetch_issue(jira_url, issue_key).await {
        Ok(issue) => println!("Issue: {:?}", issue),
        Err(e) => eprintln!("Error fetching issue: {}", e),
    }

    Ok(())
}