use reqwest;
use serde_json::Value;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2.0/search";
    let query = r#"{
        "jql": "project = YOUR_PROJECT_KEY AND assignee = currentUser() ORDER BY updated DESC",
        "fields": ["key", "summary", "status"]
    }"#;

    let response = reqwest::get(jira_url)?
        .header("Content-Type", "application/json")
        .body(query)
        .send()?;

    if response.status().is_success() {
        let issues: Vec<JiraIssue> = serde_json::from_reader(response.text()?)?;
        for issue in issues {
            println!("Key: {}, Summary: {}, Status: {}", issue.key, issue.summary, issue.status);
        }
    } else {
        eprintln!("Failed to retrieve JIRA issues: {}", response.status());
    }

    Ok(())
}