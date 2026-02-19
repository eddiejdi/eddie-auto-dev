use std::io::{self, Write};
use reqwest;
use serde_json;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_issue_success() {
        let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
        let key = "RUST-13";
        let summary = "Integrate Rust Agent with Jira - tracking of activities";
        let description = "This is a test issue to track the progress of integrating Rust Agent with Jira.";

        match create_issue(jira_url, key, summary, description) {
            Ok(issue) => assert_eq!(issue.key, key),
            Err(e) => panic!("Error creating issue: {}", e),
        }
    }

    #[test]
    fn test_create_issue_failure() {
        let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
        let key = "RUST-14";
        let summary = "";
        let description = "This is a test issue to track the progress of integrating Rust Agent with Jira.";

        match create_issue(jira_url, key, summary, description) {
            Ok(_) => panic!("Expected error creating issue"),
            Err(e) => assert!(e.is_request_error()),
        }
    }

    // Add more tests as needed
}