use reqwest;
use serde_json::Value;

#[derive(Debug)]
pub struct JiraIssue {
    pub key: String,
    pub summary: String,
    pub status: String,
}

impl JiraIssue {
    async fn get_issue(jira_url: &str, issue_key: &str) -> Result<JiraIssue, reqwest::Error> {
        let url = format!("{}rest/api/2/issue/{}", jira_url, issue_key);
        let response = reqwest::get(&url).await?;
        if !response.status().is_success() {
            return Err(reqwest::Error::from(response));
        }
        Ok(response.json::<JiraIssue>().await?)
    }
}

#[derive(Debug)]
pub struct JiraAgent {
    pub jira_url: String,
    pub issue_key: String,
    pub status: String,
}

impl JiraAgent {
    async fn track_activity(&self) -> Result<(), reqwest::Error> {
        let url = format!("{}rest/api/2/issue/{}/comment", self.jira_url, self.issue_key);
        let response = reqwest::post(&url)
            .json(json!({
                "body": "This is a test comment from Rust Agent",
            }))
            .await?;
        if !response.status().is_success() {
            return Err(reqwest::Error::from(response));
        }
        Ok(())
    }
}

#[tokio::main]
async fn main() -> Result<(), reqwest::Error> {
    let jira_url = "https://your-jira-instance.atlassian.net";
    let issue_key = "ABC-123";

    let mut agent = JiraAgent {
        jira_url,
        issue_key,
        status: String::new(),
    };

    // Get current issue details
    let current_issue = JiraIssue::get_issue(&jira_url, &issue_key).await?;
    println!("Current Issue Details:");
    println!("{:#?}", current_issue);

    // Track activity
    agent.track_activity().await?;

    Ok(())
}