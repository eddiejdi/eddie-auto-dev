use reqwest;
use serde_json;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn fetch_jira_issue(issue_key: &str) -> Result<JiraIssue, reqwest::Error> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
    let response = reqwest::get(&url).await?;
    if response.status().is_success() {
        Ok(response.json::<JiraIssue>().await?)
    } else {
        Err(reqwest::Error::from(response.text().await?))
    }
}

async fn update_jira_issue(issue_key: &str, status: &str) -> Result<(), reqwest::Error> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}/status", issue_key);
    let payload = serde_json!({
        "update": {
            "fields": {
                "status": {
                    "id": status
                }
            }
        }
    });
    reqwest::put(&url, json_payload).await?;
    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let issue_key = "YOUR-ISSUE-KEY";
    let mut issues: Vec<JiraIssue> = vec![];

    // Fetch all issues
    for i in 1..=10 { // Assuming there are up to 10 issues
        let issue = fetch_jira_issue(&format!("{}-{}", issue_key, i)).await?;
        issues.push(issue);
    }

    // Update the status of each issue
    for issue in &issues {
        update_jira_issue(issue.key.as_str(), "IN_PROGRESS").await?;
    }

    println!("Issues updated successfully!");

    Ok(())
}