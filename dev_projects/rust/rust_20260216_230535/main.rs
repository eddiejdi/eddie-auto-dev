use serde_json;
use reqwest;

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

#[derive(Debug)]
struct JiraClient {
    base_url: String,
    auth_token: String,
}

impl JiraClient {
    fn new(base_url: &str, auth_token: &str) -> Self {
        JiraClient {
            base_url: base_url.to_string(),
            auth_token: auth_token.to_string(),
        }
    }

    async fn create_issue(&self, issue: &JiraIssue) -> Result<(), reqwest::Error> {
        let url = format!("{}rest/api/2/issue", self.base_url);
        let headers = [("Authorization".to_string(), format!("Bearer {}", self.auth_token))];
        let body = issue.to_json();

        let response = reqwest::Client::new()
            .post(url)
            .headers(headers)
            .json(body)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(reqwest::Error::from(response))
        }
    }
}

#[derive(Debug)]
struct JiraCli {
    client: JiraClient,
}

impl JiraCli {
    fn new(client: JiraClient) -> Self {
        JiraCli { client }
    }

    async fn create_issue(&self, key: &str, summary: &str, status: &str) -> Result<(), reqwest::Error> {
        let issue = JiraIssue::new(key, summary, status);
        self.client.create_issue(&issue).await
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let base_url = "https://your-jira-instance.atlassian.net";
    let auth_token = "your-auth-token";
    let client = JiraClient::new(base_url, auth_token);

    let cli = JiraCli::new(client);
    cli.create_issue("JIRA-123", "Fix bug in login page", "In Progress").await?;

    println!("Issue created successfully!");

    Ok(())
}