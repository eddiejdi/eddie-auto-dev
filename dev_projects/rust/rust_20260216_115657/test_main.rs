use std::io::{self, Write};
use reqwest;
use serde_json;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let issue_key = "YOUR-ISSUE-KEY";

    // Create a new JiraIssue instance
    let mut issue = JiraIssue {
        key: issue_key.to_string(),
        summary: String::new(),
        status: String::new(),
    };

    // Fetch the issue details from Jira
    let response = reqwest::get(format!("{}{}", jira_url, issue.key))?;
    let json_response: serde_json::Value = response.json()?;

    if let Some(issue_data) = json_response["fields"].as_object().unwrap() {
        issue.summary = issue_data.get("summary").map_or(String::new(), |v| v.as_str().unwrap().to_string());
        issue.status = issue_data.get("status").map_or(String::new(), |v| v.as_str().unwrap().to_string());
    }

    // Print the issue details
    println!("Issue Key: {}", issue.key);
    println!("Summary: {}", issue.summary);
    println!("Status: {}", issue.status);

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fetch_issue_success() {
        let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
        let issue_key = "YOUR-ISSUE-KEY";

        // Create a new JiraIssue instance
        let mut issue = JiraIssue {
            key: issue_key.to_string(),
            summary: String::new(),
            status: String::new(),
        };

        // Mock the response from reqwest
        let mock_response = serde_json::json!({
            "fields": {
                "summary": "Test Issue",
                "status": "Open"
            }
        });

        let mut mock_client = reqwest::Client::new();
        mock_client.get(jira_url).send().unwrap().body(mock_response.to_string()).unwrap();

        // Call the main function
        main().expect("main function should not fail");

        assert_eq!(issue.key, "YOUR-ISSUE-KEY");
        assert_eq!(issue.summary, "Test Issue");
        assert_eq!(issue.status, "Open");
    }

    #[test]
    fn test_fetch_issue_failure() {
        let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
        let issue_key = "YOUR-ISSUE-KEY";

        // Create a new JiraIssue instance
        let mut issue = JiraIssue {
            key: issue_key.to_string(),
            summary: String::new(),
            status: String::new(),
        };

        // Mock the response from reqwest with an error
        let mock_error = serde_json::json!({
            "error": {
                "message": "Not Found"
            }
        });

        let mut mock_client = reqwest::Client::new();
        mock_client.get(jira_url).send().unwrap_err();

        // Call the main function
        main().expect("main function should not fail");

        assert_eq!(issue.key, "YOUR-ISSUE-KEY");
        assert_eq!(issue.summary, String::new());
        assert_eq!(issue.status, String::new());
    }
}