use std::collections::HashMap;
use reqwest::{Client, Error};
use serde_json::Value;

struct JiraIntegration {
    client: Client,
}

impl JiraIntegration {
    fn new() -> Result<Self, Error> {
        Ok(JiraIntegration {
            client: Client::new(),
        })
    }

    async fn get_issues(&self) -> Result<Vec<Value>, Error> {
        let response = self.client.get("https://your-jira-instance.atlassian.net/rest/api/2/search").send().await?;
        let json: Value = response.json().await?;

        if !json["issues"].is_array() {
            return Err(Error::from("Invalid JSON response"));
        }

        Ok(json["issues"].as_array()?.iter().cloned().collect())
    }
}

#[derive(Debug)]
struct Issue {
    key: String,
    summary: String,
    status: String,
}

fn main() -> Result<(), Error> {
    let integration = JiraIntegration::new()?;
    let issues = integration.get_issues().await?;

    for issue in issues {
        println!("Key: {}", issue["key"].as_str().unwrap());
        println!("Summary: {}", issue["fields"]["summary"].as_str().unwrap());
        println!("Status: {}", issue["fields"]["status"]["name"].as_str().unwrap());
        println!();
    }

    Ok(())
}