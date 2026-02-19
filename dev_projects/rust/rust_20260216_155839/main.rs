use reqwest::Client;
use serde_json::{Value, Map};
use std::collections::HashMap;

struct Jira {
    client: Client,
}

impl Jira {
    fn new(api_key: &str) -> Self {
        Jira {
            client: Client::new(),
        }
    }

    async fn get_project(&self, project_id: &str) -> Result<Map<String, Value>, reqwest::Error> {
        let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/project/{}/", project_id);
        let response = self.client.get(url).send().await?;
        response.json().await
    }

    async fn create_issue(&self, issue: &Issue) -> Result<(), reqwest::Error> {
        let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/");
        let response = self.client.post(url).json(issue).send().await?;
        response.text().await
    }
}

#[derive(serde::Serialize)]
struct Issue {
    fields: Map<String, Value>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira = Jira::new("your-api-key");
    let project_id = "YOUR_PROJECT_ID";
    let issue_fields = HashMap::from([
        ("summary".to_string(), Value::String("New Rust Agent Task".to_string())),
        ("description".to_string(), Value::String("Implement a Rust agent for monitoring and managing activities in Rust.")),
        ("issuetype".to_string(), Value::Object(Map::from([
            ("name".to_string(), Value::String("Bug".to_string())),
        ]))),
    ]);

    let issue = Issue { fields: issue_fields };
    jira.create_issue(&issue).await?;

    println!("Issue created successfully!");

    Ok(())
}