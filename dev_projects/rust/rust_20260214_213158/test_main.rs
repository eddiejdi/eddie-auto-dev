use reqwest;
use serde_json;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn fetch_issue_from_jira(jira_url: &str, issue_key: &str) -> Result<JiraIssue, reqwest::Error> {
    let response = reqwest::get(format!("{}rest/api/2/issue/{}", jira_url, issue_key))
        .await?;

    if !response.status().is_success() {
        return Err(reqwest::Error::from(response));
    }

    let json: serde_json::Value = response.json().await?;
    Ok(JiraIssue {
        key: json["key"].as_str().unwrap().to_string(),
        summary: json["fields"]["summary"].as_str().unwrap().to_string(),
        status: json["fields"]["status"]["name"].as_str().unwrap().to_string(),
    })
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net";
    let issue_key = "ABC-123";

    match fetch_issue_from_jira(jira_url, issue_key).await {
        Ok(issue) => println!("Issue: {:?}", issue),
        Err(e) => eprintln!("Error fetching issue: {}", e),
    }

    Ok(())
}