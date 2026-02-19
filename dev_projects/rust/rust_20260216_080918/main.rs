use reqwest;
use serde_json::Value;
use chrono::{DateTime, Utc};
use clap::{App, Arg};

struct JiraClient {
    token: String,
}

impl JiraClient {
    fn new(token: String) -> Self {
        JiraClient { token }
    }

    async fn get_issues(&self) -> Result<Vec<Value>, reqwest::Error> {
        let url = "https://your-jira-instance.atlassian.net/rest/api/2/search";
        let response = reqwest::get(url)
            .header("Authorization", &format!("Basic {}", base64::encode(format!("{}:{}", self.token, ""))))
            .send()
            .await?;

        if response.status().is_success() {
            Ok(response.json::<Vec<Value>>().await?)
        } else {
            Err(reqwest::Error::new(reqwest::StatusCode::from(response.status()), "Failed to retrieve issues"))
        }
    }

    async fn create_issue(&self, issue: &Value) -> Result<(), reqwest::Error> {
        let url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
        let response = reqwest::post(url)
            .header("Authorization", &format!("Basic {}", base64::encode(format!("{}:{}", self.token, ""))))
            .json(issue)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(reqwest::Error::new(reqwest::StatusCode::from(response.status()), "Failed to create issue"))
        }
    }

    async fn update_issue(&self, issue_key: &str, issue: &Value) -> Result<(), reqwest::Error> {
        let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}/update", issue_key);
        let response = reqwest::put(url)
            .header("Authorization", &format!("Basic {}", base64::encode(format!("{}:{}", self.token, ""))))
            .json(issue)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(reqwest::Error::new(reqwest::StatusCode::from(response.status()), "Failed to update issue"))
        }
    }

    async fn get_issue(&self, issue_key: &str) -> Result<Value, reqwest::Error> {
        let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
        let response = reqwest::get(url)
            .header("Authorization", &format!("Basic {}", base64::encode(format!("{}:{}", self.token, ""))))
            .send()
            .await?;

        if response.status().is_success() {
            Ok(response.json::<Value>>().await?)
        } else {
            Err(reqwest::Error::new(reqwest::StatusCode::from(response.status()), "Failed to retrieve issue"))
        }
    }

    async fn delete_issue(&self, issue_key: &str) -> Result<(), reqwest::Error> {
        let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
        let response = reqwest::delete(url)
            .header("Authorization", &format!("Basic {}", base64::encode(format!("{}:{}", self.token, ""))))
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(reqwest::Error::new(reqwest::StatusCode::from(response.status()), "Failed to delete issue"))
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let app = App::new("Jira Agent")
        .version("1.0")
        .author("Your Name")
        .about("Integrates Rust Agent with Jira for tracking activities in Rust.");

    let args = app.get_matches();

    if args.is_present("create") {
        let issue = serde_json::from_str::<Value>(&args.value_of("issue").unwrap())?;
        let client = JiraClient::new(args.value_of("token").unwrap());
        client.create_issue(&issue).await?;
        println!("Issue created successfully.");
    } else if args.is_present("update") {
        let issue_key = args.value_of("issue_key").unwrap();
        let issue = serde_json::from_str::<Value>(&args.value_of("issue").unwrap())?;
        let client = JiraClient::new(args.value_of("token").unwrap());
        client.update_issue(issue_key, &issue).await?;
        println!("Issue updated successfully.");
    } else if args.is_present("delete") {
        let issue_key = args.value_of("issue_key").unwrap();
        let client = JiraClient::new(args.value_of("token").unwrap());
        client.delete_issue(issue_key).await?;
        println!("Issue deleted successfully.");
    } else if args.is_present("get") {
        let issue_key = args.value_of("issue_key").unwrap();
        let client = JiraClient::new(args.value_of("token").unwrap());
        let issue = client.get_issue(issue_key).await?;
        println!("{:?}", issue);
    } else {
        eprintln!("Usage: jira-agent [create|update|delete|get] --issue <json>");
    }

    Ok(())
}