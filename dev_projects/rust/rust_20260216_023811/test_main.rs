use reqwest;
use serde_json::{self, Value};
use tokio::sync::mpsc;

struct JiraClient {
    client: reqwest::Client,
}

impl JiraClient {
    async fn new() -> Self {
        JiraClient {
            client: reqwest::Client::new(),
        }
    }

    async fn get_issues(&self, project_key: &str) -> Result<Vec<Value>, reqwest::Error> {
        let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/project/{}/issue", project_key);
        self.client.get(url).send().await?.json()
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = JiraClient::new().await?;

    let mut issues_channel = mpsc::channel(10);

    tokio::spawn(async move {
        let project_key = "YOUR_PROJECT_KEY";
        let issues = client.get_issues(project_key).await?;
        for issue in issues {
            issues_channel.send(issue).await.unwrap();
        }
    });

    while let Ok(issue) = issues_channel.recv().await {
        println!("{:?}", issue);
    }

    Ok(())
}

#[tokio::test]
async fn test_get_issues_success() {
    let client = JiraClient::new().await?;
    let project_key = "YOUR_PROJECT_KEY";
    let response = client.get_issues(project_key).await?;

    assert_eq!(response.len(), 10); // Assuming there are 10 issues in the response
}

#[tokio::test]
async fn test_get_issues_error() {
    let client = JiraClient::new().await?;
    let project_key = "INVALID_PROJECT_KEY";
    let result = client.get_issues(project_key).await;

    assert!(result.is_err());
}