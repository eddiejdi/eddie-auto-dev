use std::io::{self, Write};
use reqwest;
use serde_json;

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

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_key = "ABC-123";
    let jira_summary = "Fix bug in login page";
    let jira_status = "In Progress";

    let issue = JiraIssue::new(jira_key, jira_summary, jira_status);

    let json_data = issue.to_json();

    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", jira_key);
    let response = reqwest::Client::new()
        .post(url)
        .json(&json_data)
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

    #[test]
    fn test_new_with_valid_values() {
        let key = "ABC-123";
        let summary = "Fix bug in login page";
        let status = "In Progress";

        let issue = JiraIssue::new(key, summary, status);

        assert_eq!(issue.key, key);
        assert_eq!(issue.summary, summary);
        assert_eq!(issue.status, status);
    }

    #[test]
    fn test_new_with_invalid_values() {
        let key = "";
        let summary = "Fix bug in login page";
        let status = "";

        match JiraIssue::new(key, summary, status) {
            Err(_) => {}
            _ => panic!("Expected to fail with invalid values"),
        }
    }

    #[test]
    fn test_to_json_with_valid_values() {
        let key = "ABC-123";
        let summary = "Fix bug in login page";
        let status = "In Progress";

        let issue = JiraIssue::new(key, summary, status);

        let json_data = issue.to_json();

        assert_eq!(json_data["key"], key);
        assert_eq!(json_data["summary"], summary);
        assert_eq!(json_data["status"], status);
    }

    #[test]
    fn test_to_json_with_invalid_values() {
        let key = "";
        let summary = "Fix bug in login page";
        let status = "";

        match issue.to_json() {
            Err(_) => {}
            _ => panic!("Expected to fail with invalid values"),
        }
    }
}