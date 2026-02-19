use std::io;
use reqwest::{Client, Error};
use serde_json;

struct Jira {
    url: String,
    username: String,
    password: String,
}

impl Jira {
    fn new(url: &str, username: &str, password: &str) -> Result<Self, Error> {
        Ok(Jira {
            url: url.to_string(),
            username: username.to_string(),
            password: password.to_string(),
        })
    }

    async fn create_issue(&self, issue_data: serde_json::Value) -> Result<(), Error> {
        let client = Client::new();
        let response = client
            .post(&format!("{}rest/api/2/issue", self.url))
            .basic_auth(&self.username, &self.password)
            .json(&issue_data)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(Error::from(response.text().await.unwrap()))
        }
    }
}

#[derive(serde::Serialize)]
struct IssueData {
    fields: serde_json::Value,
}

fn main() -> Result<(), Error> {
    let jira = Jira::new("https://your-jira-instance.atlassian.net", "username", "password")?;

    let issue_data = IssueData {
        fields: serde_json::json!({
            "project": { "key": "YOUR_PROJECT_KEY" },
            "summary": "Test issue",
            "description": "This is a test issue created by Rust Agent",
            "issuetype": { "name": "Bug" }
        }),
    };

    jira.create_issue(issue_data).await?;

    println!("Issue created successfully");

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_issue_success() {
        let jira = Jira::new("https://your-jira-instance.atlassian.net", "username", "password").unwrap();
        let issue_data = IssueData {
            fields: serde_json::json!({
                "project": { "key": "YOUR_PROJECT_KEY" },
                "summary": "Test issue",
                "description": "This is a test issue created by Rust Agent",
                "issuetype": { "name": "Bug" }
            }),
        };

        assert!(jira.create_issue(issue_data).is_ok());
    }

    #[test]
    fn test_create_issue_failure() {
        let jira = Jira::new("https://your-jira-instance.atlassian.net", "username", "password").unwrap();
        let issue_data = IssueData {
            fields: serde_json::json!({
                "project": { "key": "YOUR_PROJECT_KEY" },
                "summary": "",
                "description": "",
                "issuetype": { "name": "Bug" }
            }),
        };

        assert!(jira.create_issue(issue_data).is_err());
    }

    #[test]
    fn test_create_issue_division_by_zero() {
        let jira = Jira::new("https://your-jira-instance.atlassian.net", "username", "password").unwrap();
        let issue_data = IssueData {
            fields: serde_json::json!({
                "project": { "key": "YOUR_PROJECT_KEY" },
                "summary": "Test issue",
                "description": "This is a test issue created by Rust Agent",
                "issuetype": { "name": "Bug" }
            }),
        };

        assert!(jira.create_issue(issue_data).is_err());
    }

    #[test]
    fn test_create_issue_invalid_json() {
        let jira = Jira::new("https://your-jira-instance.atlassian.net", "username", "password").unwrap();
        let issue_data = IssueData {
            fields: serde_json::json!({
                "project": { "key": "YOUR_PROJECT_KEY" },
                "summary": "",
                "description": "",
                "issuetype": { "name": "Bug" }
            }),
        };

        assert!(jira.create_issue(issue_data).is_err());
    }

    #[test]
    fn test_create_issue_edge_case() {
        let jira = Jira::new("https://your-jira-instance.atlassian.net", "username", "password").unwrap();
        let issue_data = IssueData {
            fields: serde_json::json!({
                "project": { "key": "YOUR_PROJECT_KEY" },
                "summary": "",
                "description": "",
                "issuetype": { "name": "Bug" }
            }),
        };

        assert!(jira.create_issue(issue_data).is_err());
    }
}