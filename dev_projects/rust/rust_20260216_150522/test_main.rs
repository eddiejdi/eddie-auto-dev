#[cfg(test)]
mod tests {
    use reqwest;
    use serde_json::Value;

    #[derive(Debug)]
    struct JiraIssue {
        key: String,
        summary: String,
        status: String,
    }

    fn fetch_jira_issue(issue_key: &str) -> Result<JiraIssue, Box<dyn std::error::Error>> {
        let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
        let response = reqwest::get(&url)?;

        if !response.status().is_success() {
            return Err(format!("Failed to fetch JIRA issue: {}", response.text()).into());
        }

        let json_response: Value = serde_json::from_str(&response.text())?;
        let issue_data = json_response["fields"];

        Ok(JiraIssue {
            key: issue_data["key"].as_str().unwrap().to_string(),
            summary: issue_data["summary"].as_str().unwrap().to_string(),
            status: issue_data["status"]["name"].as_str().unwrap().to_string(),
        })
    }

    #[test]
    fn test_fetch_jira_issue_success() {
        let issue_key = "ABC-123";
        let result = fetch_jira_issue(issue_key);
        assert!(result.is_ok());
        let issue = result.unwrap();
        assert_eq!(issue.key, "ABC-123");
        assert_eq!(issue.summary, "Test Issue");
        assert_eq!(issue.status, "To Do");
    }

    #[test]
    fn test_fetch_jira_issue_error() {
        let issue_key = "XYZ-456";
        let result = fetch_jira_issue(issue_key);
        assert!(result.is_err());
        let err = result.err().unwrap();
        assert_eq!(err.to_string(), "Failed to fetch JIRA issue: Not Found");
    }

    #[test]
    fn test_fetch_jira_issue_edge_case() {
        let issue_key = "";
        let result = fetch_jira_issue(issue_key);
        assert!(result.is_err());
        let err = result.err().unwrap();
        assert_eq!(err.to_string(), "Failed to fetch JIRA issue: Not Found");
    }
}