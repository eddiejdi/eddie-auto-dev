use reqwest;
use serde_json;
use clap::{App, Arg};
use std::str;

struct JiraClient {
    token: String,
}

impl JiraClient {
    fn new(token: String) -> Self {
        JiraClient { token }
    }

    async fn create_issue(&self, issue_data: &serde_json::Value) -> Result<serde_json::Value, reqwest::Error> {
        let url = "https://your-jira-instance.atlassian.net/rest/api/3/issue";
        let response = reqwest::Client::new()
            .post(url)
            .header("Authorization", format!("Basic {}", base64::encode(format!("{}:{}", self.token, ""))))
            .json(issue_data)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(response.json().await?)
        } else {
            Err(reqwest::Error::from(response.text().await.unwrap()))
        }
    }
}

fn main() {
    let app = App::new("Jira Scrum-12")
        .version("0.1.0")
        .author("Your Name <your.email@example.com>")
        .about("Integrates Rust Agent with Jira in Rust");

    let token = app.arg(
        Arg::new("token")
            .long("token")
            .takes_value(true)
            .help("Jira API Token"),
    );

    let issue_data = app.arg(
        Arg::new("issue-data")
            .long("issue-data")
            .takes_value(true)
            .help("Issue data in JSON format"),
    );

    if let Ok(token) = token.value() {
        if let Ok(issue_data) = issue_data.value() {
            let client = JiraClient::new(token);
            let issue_json: serde_json::Value = serde_json::from_str(issue_data)?;
            match client.create_issue(&issue_json).await {
                Ok(response) => println!("Issue created successfully: {:?}", response),
                Err(err) => eprintln!("Error creating issue: {}", err),
            }
        } else {
            println!("Invalid issue data format");
        }
    } else {
        println!("Please provide a Jira API Token");
    }
}

#[tokio::test]
async fn test_create_issue_success() {
    let client = JiraClient::new("your-jira-token".to_string());
    let issue_data = r#"{
        "fields": {
            "project": {
                "key": "YOUR_PROJECT_KEY"
            },
            "summary": "Test Issue",
            "description": "This is a test issue created by Rust Agent.",
            "issuetype": {
                "name": "Bug"
            }
        }
    }"#;

    let response = client.create_issue(&serde_json::from_str(issue_data).unwrap()).await.unwrap();
    assert_eq!(response["key"], "YOUR_PROJECT_KEY-12345");
}

#[tokio::test]
async fn test_create_issue_failure() {
    let client = JiraClient::new("your-jira-token".to_string());
    let issue_data = r#"{
        "fields": {
            "project": {
                "key": "YOUR_PROJECT_KEY"
            },
            "summary": "",
            "description": "",
            "issuetype": {
                "name": ""
            }
        }
    }"#;

    let response = client.create_issue(&serde_json::from_str(issue_data).unwrap()).await;
    assert!(response.is_err());
}

#[tokio::test]
async fn test_create_issue_invalid_token() {
    let client = JiraClient::new("invalid-token".to_string());
    let issue_data = r#"{
        "fields": {
            "project": {
                "key": "YOUR_PROJECT_KEY"
            },
            "summary": "Test Issue",
            "description": "This is a test issue created by Rust Agent.",
            "issuetype": {
                "name": "Bug"
            }
        }
    }"#;

    let response = client.create_issue(&serde_json::from_str(issue_data).unwrap()).await;
    assert!(response.is_err());
}