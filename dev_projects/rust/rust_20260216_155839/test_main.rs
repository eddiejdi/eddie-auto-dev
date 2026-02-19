use reqwest::Error;
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

    async fn get_project(&self, project_id: &str) -> Result<Map<String, Value>, Error> {
        let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/project/{}/", project_id);
        self.client.get(url).send().await?
            .json()
    }

    async fn create_issue(&self, issue: &Issue) -> Result<(), Error> {
        let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/");
        self.client.post(url).json(issue).send().await
    }
}

#[derive(serde::Serialize)]
struct Issue {
    fields: Map<String, Value>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Teste para get_project com sucesso
    let jira = Jira::new("your-api-key");
    let project_id = "YOUR_PROJECT_ID";
    let expected_response = serde_json::from_str(r#"{...}"#).unwrap(); // Substitua pelo corpo esperado da resposta
    assert_eq!(jira.get_project(project_id).await?, expected_response);

    // Teste para create_issue com sucesso
    let issue_fields = HashMap::from([
        ("summary".to_string(), Value::String("New Rust Agent Task".to_string())),
        ("description".to_string(), Value::String("Implement a Rust agent for monitoring and managing activities in Rust.")),
        ("issuetype".to_string(), Value::Object(Map::from([
            ("name".to_string(), Value::String("Bug".to_string())),
        ]))),
    ]);
    let issue = Issue { fields: issue_fields };
    assert!(jira.create_issue(&issue).await.is_ok());

    println!("All tests passed!");

    Ok(())
}