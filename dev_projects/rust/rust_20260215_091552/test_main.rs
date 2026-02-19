use std::io::{self, Write};
use serde_json;
use reqwest;

#[derive(Serialize, Deserialize)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let username = "your-username";
    let password = "your-password";

    let issue_data = JiraIssue {
        key: "ABC-123".to_string(),
        summary: "Rust Agent Integration Test",
        status: "Open".to_string(),
    };

    let headers = [("Authorization", format!("Basic {}", base64::encode(format!("{}:{}", username, password)))).into_iter().collect()];
    let response = reqwest::post(jira_url)
        .headers(headers)
        .json(&issue_data)
        .send()?;

    if response.status().is_success() {
        println!("Issue created successfully!");
    } else {
        eprintln!("Failed to create issue: {}", response.text()?);
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;
    use reqwest::{Error, Response};

    #[test]
    fn test_create_issue_success() -> Result<(), Box<dyn Error>> {
        let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
        let username = "your-username";
        let password = "your-password";

        let issue_data = JiraIssue {
            key: "ABC-123".to_string(),
            summary: "Rust Agent Integration Test",
            status: "Open".to_string(),
        };

        let headers = [("Authorization", format!("Basic {}", base64::encode(format!("{}:{}", username, password)))).into_iter().collect()];
        let response = reqwest::post(jira_url)
            .headers(headers)
            .json(&issue_data)
            .send()?;

        assert!(response.status().is_success());
        Ok(())
    }

    #[test]
    fn test_create_issue_failure() -> Result<(), Box<dyn Error>> {
        let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
        let username = "your-username";
        let password = "your-password";

        let issue_data = JiraIssue {
            key: "ABC-123".to_string(),
            summary: "Rust Agent Integration Test",
            status: "Open".to_string(),
        };

        let headers = [("Authorization", format!("Basic {}", base64::encode(format!("{}:{}", username, password)))).into_iter().collect()];
        let response = reqwest::post(jira_url)
            .headers(headers)
            .json(&issue_data)
            .send()?;

        assert!(!response.status().is_success());
        Ok(())
    }
}