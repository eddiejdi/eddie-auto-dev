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

#[derive(Debug)]
struct JiraAgent {
    token: String,
    issue_key: String,
}

impl JiraAgent {
    async fn track_activity(&self) -> Result<(), reqwest::Error> {
        let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}/comment", self.issue_key);
        let response = reqwest::post(&url)
            .header("Authorization", &format!("Bearer {}", self.token))
            .json(&serde_json!({
                "body": "This is a test comment from Rust Agent",
            }))
            .await?;
        if response.status().is_success() {
            Ok(())
        } else {
            Err(reqwest::Error::from(response.status()))
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), reqwest::Error> {
    let token = "your-jira-token";
    let issue_key = "YOUR-ISSUE-KEY";

    let agent = JiraAgent { token, issue_key };
    agent.track_activity().await?;

    println!("Activity tracked successfully!");

    Ok(())
}