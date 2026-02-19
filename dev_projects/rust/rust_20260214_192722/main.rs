use reqwest;
use serde_json;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn fetch_jira_issue(issue_key: &str) -> Result<JiraIssue, reqwest::Error> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
    let response = reqwest::get(&url).await?;
    if response.status().is_success() {
        let json: serde_json::Value = response.json().await?;
        Ok(JiraIssue {
            key: json["key"].as_str().unwrap().to_string(),
            summary: json["fields"]["summary"].as_str().unwrap().to_string(),
            status: json["fields"]["status"]["name"].as_str().unwrap().to_string(),
        })
    } else {
        Err(reqwest::Error::from(response.status()))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let issue_key = "ABC-123";
    let issue = fetch_jira_issue(issue_key).await?;

    println!("Issue Key: {}", issue.key);
    println!("Summary: {}", issue.summary);
    println!("Status: {}", issue.status);

    Ok(())
}