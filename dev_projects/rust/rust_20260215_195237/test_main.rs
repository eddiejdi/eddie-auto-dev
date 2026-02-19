use reqwest;
use serde_json;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn get_jira_issue(issue_key: &str) -> Result<JiraIssue, reqwest::Error> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
    let response = reqwest::get(&url).await?;
    if response.status().is_success() {
        Ok(response.json::<JiraIssue>().await?)
    } else {
        Err(reqwest::Error::from(response.text().await.unwrap()))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let issue_key = "ABC-123";
    let jira_issue = get_jira_issue(issue_key).await?;

    println!("JIRA Issue: {:?}", jira_issue);

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_get_jira_issue_success() {
        let issue_key = "ABC-123";
        let response = reqwest::get("https://your-jira-instance.atlassian.net/rest/api/2/issue/ABC-123").await.unwrap();
        assert_eq!(response.status(), reqwest::StatusCode::OK);
    }

    #[tokio::test]
    async fn test_get_jira_issue_error() {
        let issue_key = "ABC-123";
        let response = reqwest::get("https://your-jira-instance.atlassian.net/rest/api/2/issue/ABC-123").await.unwrap();
        assert_eq!(response.status(), reqwest::StatusCode::NOT_FOUND);
    }

    #[tokio::test]
    async fn test_get_jira_issue_invalid_key() {
        let issue_key = "XYZ";
        let response = reqwest::get("https://your-jira-instance.atlassian.net/rest/api/2/issue/XYZ").await.unwrap();
        assert_eq!(response.status(), reqwest::StatusCode::NOT_FOUND);
    }

    #[tokio::test]
    async fn test_get_jira_issue_invalid_status() {
        let issue_key = "ABC-123";
        let response = reqwest::get("https://your-jira-instance.atlassian.net/rest/api/2/issue/ABC-123").await.unwrap();
        assert_eq!(response.status(), reqwest::StatusCode::NOT_FOUND);
    }

    #[tokio::test]
    async fn test_get_jira_issue_invalid_response() {
        let issue_key = "ABC-123";
        let response = reqwest::get("https://your-jira-instance.atlassian.net/rest/api/2/issue/ABC-123").await.unwrap();
        assert_eq!(response.status(), reqwest::StatusCode::NOT_FOUND);
    }
}