use reqwest;
use serde_json;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

fn fetch_jira_issue(issue_key: &str) -> Result<JiraIssue, Box<dyn std::error::Error>> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}/", issue_key);
    let response = reqwest::get(&url)?;

    if !response.status().is_success() {
        return Err(Box::new(reqwest::Error::from(response.status())));
    }

    let issue_data: serde_json::Value = response.json()?;
    let issue = serde_json::from_value(issue_data)?;

    Ok(JiraIssue {
        key: issue["key"].as_str().unwrap().to_string(),
        summary: issue["fields"]["summary"].as_str().unwrap().to_string(),
        status: issue["fields"]["status"]["name"].as_str().unwrap().to_string(),
    })
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let issue_key = "ABC-123";
    let issue = fetch_jira_issue(issue_key)?;

    println!("Issue Key: {}", issue.key);
    println!("Summary: {}", issue.summary);
    println!("Status: {}", issue.status);

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fetch_jira_issue_success() {
        let issue_key = "ABC-123";
        let response = reqwest::mock("GET", format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}/", issue_key))
            .with_status(200)
            .with_body(r#"{
                "key": "ABC-123",
                "fields": {
                    "summary": "Test Issue",
                    "status": {
                        "name": "Open"
                    }
                }
            }"#)
            .create();

        let issue = fetch_jira_issue(issue_key).unwrap();
        assert_eq!(issue.key, "ABC-123");
        assert_eq!(issue.summary, "Test Issue");
        assert_eq!(issue.status, "Open");
    }

    #[test]
    fn test_fetch_jira_issue_error() {
        let response = reqwest::mock("GET", format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}/", "ABC-123"))
            .with_status(404)
            .create();

        let result = fetch_jira_issue("ABC-123");
        assert!(result.is_err());
    }
}