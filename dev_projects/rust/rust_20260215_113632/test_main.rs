use reqwest;
use serde_json::Value;

struct JiraClient {
    base_url: String,
}

impl JiraClient {
    fn new(base_url: &str) -> Self {
        JiraClient { base_url: base_url.to_string() }
    }

    async fn create_issue(&self, issue_data: Value) -> Result<Value, reqwest::Error> {
        let response = self
            .client()
            .post(format!("{}rest/api/2/issue", &self.base_url))
            .json(issue_data)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(response.json().await?)
        } else {
            Err(reqwest::Error::from(response.text().await.unwrap()))
        }
    }

    fn client(&self) -> reqwest::Client {
        reqwest::ClientBuilder::new()
            .base_url(self.base_url.clone())
            .build()
            .unwrap()
    }
}

#[derive(serde::Serialize)]
struct IssueData {
    project: String,
    summary: String,
    description: String,
    issuetype: String,
    priority: String,
    assignee: Option<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net");

    let issue_data = IssueData {
        project: "YOUR_PROJECT_KEY".to_string(),
        summary: "New Rust Agent Integration".to_string(),
        description: "This is a new integration of the Rust Agent with Jira for tracking activities.".to_string(),
        issuetype: "Task".to_string(),
        priority: "High".to_string(),
        assignee: Some("your-username".to_string()),
    };

    let response = jira_client.create_issue(issue_data).await?;

    println!("Issue created successfully: {:?}", response);

    Ok(())
}