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