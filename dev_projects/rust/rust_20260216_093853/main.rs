use reqwest;
use serde_json::Value;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn fetch_jira_issue(issue_key: &str) -> Result<JiraIssue, Box<dyn std::error::Error>> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
    let response = reqwest::get(&url).await?;
    if !response.status().is_success() {
        return Err(format!("Failed to fetch JIRA issue: {}", response.text().await?).into());
    }
    let json: Value = serde_json::from_str(&response.text().await?)?;
    Ok(JiraIssue {
        key: json["key"].as_str()?.to_string(),
        summary: json["fields"]["summary"].as_str()?.to_string(),
        status: json["fields"]["status"]["name"].as_str()?.to_string(),
    })
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let issue_key = "ABC-123";
    let jira_issue = fetch_jira_issue(issue_key).await?;
    println!("{:?}", jira_issue);
    Ok(())
}