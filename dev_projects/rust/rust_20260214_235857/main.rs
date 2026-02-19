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

    async fn create_issue(&self, jira_url: &str, username: &str, password: &str) -> Result<(), reqwest::Error> {
        let payload = serde_json!({
            "fields": {
                "project": {"key": self.key},
                "summary": self.summary,
                "status": {"name": self.status}
            }
        });

        let response = reqwest::Client::new()
            .post(format!("{}rest/api/2/issue", jira_url))
            .basic_auth(username, password)
            .json(&payload)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(reqwest::Error::from(response.text().await.unwrap()))
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net";
    let username = "your-username";
    let password = "your-password";

    let issue = JiraIssue::new("ABC-123", "Fix bug in the login page", "In Progress");

    issue.create_issue(jira_url, username, password).await?;

    println!("Issue created successfully!");

    Ok(())
}