use reqwest;
use serde_json::Value;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn fetch_issue(issue_key: &str) -> Result<JiraIssue, reqwest::Error> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
    let response = reqwest::get(&url).await?;
    if !response.status().is_success() {
        return Err(reqwest::Error::from(response));
    }
    let json: Value = response.json().await?;
    Ok(JiraIssue {
        key: json["key"].as_str().unwrap().to_string(),
        summary: json["fields"]["summary"].as_str().unwrap().to_string(),
        status: json["fields"]["status"]["name"].as_str().unwrap().to_string(),
    })
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let issue_key = "RUST-12";
    let issue = fetch_issue(issue_key).await?;
    println!("Issue: {}", issue);
    Ok(())
}