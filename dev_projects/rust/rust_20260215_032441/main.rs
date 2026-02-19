use reqwest;
use serde_json;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

impl JiraIssue {
    fn new(key: &str, summary: &str, status: &str) -> Self {
        JiraIssue {
            key: key.to_string(),
            summary: summary.to_string(),
            status: status.to_string(),
        }
    }

    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "key": self.key,
            "summary": self.summary,
            "status": self.status
        })
    }
}

async fn send_jira_issue(issue: JiraIssue, url: &str) -> Result<(), Box<dyn std::error::Error>> {
    let json = issue.to_json();
    let response = reqwest::post(url)
        .json(json)
        .send()?;

    if response.status().is_success() {
        Ok(())
    } else {
        Err(format!("Failed to send Jira issue: {}", response.text()).into())
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let jira_issue = JiraIssue::new("JIRA-123", "Implement Rust Agent with Jira", "In Progress");

    send_jira_issue(jira_issue, url).await?;

    println!("Jira issue sent successfully!");

    Ok(())
}