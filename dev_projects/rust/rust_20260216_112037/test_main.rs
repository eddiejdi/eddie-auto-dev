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

async fn post_jira_issue(issue: JiraIssue, url: &str) -> Result<(), reqwest::Error> {
    let response = reqwest::Client::new()
        .post(url)
        .json(&issue.to_json())
        .send()?;

    if response.status().is_success() {
        Ok(())
    } else {
        Err(reqwest::Error::from(response))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/3/issue";
    let issue_key = "YOUR-ISSUE-KEY";
    let issue_summary = "Task Description";
    let issue_status = "In Progress";

    let issue = JiraIssue::new(issue_key, issue_summary, issue_status);

    post_jira_issue(issue, jira_url).await?;

    println!("Issue posted successfully!");

    Ok(())
}

// Testes

#[tokio::test]
async fn test_post_jira_issue_success() {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/3/issue";
    let issue_key = "YOUR-ISSUE-KEY";
    let issue_summary = "Task Description";
    let issue_status = "In Progress";

    let issue = JiraIssue::new(issue_key, issue_summary, issue_status);

    post_jira_issue(issue, jira_url).await.expect("Failed to post issue");
}

#[tokio::test]
async fn test_post_jira_issue_failure() {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/3/issue";
    let issue_key = "YOUR-ISSUE-KEY";
    let issue_summary = "Task Description";
    let issue_status = "In Progress";

    let issue = JiraIssue::new(issue_key, issue_summary, issue_status);

    post_jira_issue(issue, jira_url).await.expect_err("Expected to fail");
}

#[tokio::test]
async fn test_post_jira_issue_invalid_data() {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/3/issue";
    let issue_key = "YOUR-ISSUE-KEY";
    let issue_summary = "";
    let issue_status = "";

    let issue = JiraIssue::new(issue_key, issue_summary, issue_status);

    post_jira_issue(issue, jira_url).await.expect_err("Expected to fail");
}