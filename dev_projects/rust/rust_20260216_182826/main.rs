use reqwest;
use serde_json;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    description: String,
}

impl JiraIssue {
    fn new(key: &str, summary: &str, description: &str) -> Self {
        JiraIssue {
            key: key.to_string(),
            summary: summary.to_string(),
            description: description.to_string(),
        }
    }

    async fn create_issue(&self, jira_url: &str, auth_token: &str) -> Result<(), reqwest::Error> {
        let issue_data = serde_json!({
            "fields": {
                "project": {"key": "YOUR_PROJECT_KEY"},
                "summary": self.summary.clone(),
                "description": self.description.clone(),
            }
        });

        let response = reqwest::post(format!("{}/rest/api/2/issue", jira_url))
            .header("Authorization", format!("Basic {}", auth_token))
            .json(issue_data)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(reqwest::Error::from(response.text().await.unwrap()))
        }
    }
}

#[derive(Debug)]
struct JiraClient {
    jira_url: String,
    auth_token: String,
}

impl JiraClient {
    fn new(jira_url: &str, auth_token: &str) -> Self {
        JiraClient {
            jira_url: jira_url.to_string(),
            auth_token: auth_token.to_string(),
        }
    }

    async fn create_issue(&self, issue_key: &str, summary: &str, description: &str) -> Result<(), reqwest::Error> {
        let issue = JiraIssue::new(issue_key, summary, description);
        issue.create_issue(&self.jira_url, &self.auth_token).await
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "YOUR_AUTH_TOKEN");
    let issue_key = "ABC-123";
    let summary = "Bug in the login page";
    let description = "The user cannot log in to the application.";

    jira_client.create_issue(issue_key, summary, description).await?;

    println!("Issue created successfully!");

    Ok(())
}