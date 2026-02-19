use reqwest;
use serde_json::Value;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/search";
    let query = "project=YOUR_PROJECT_KEY AND assignee=currentuser()";

    let response = reqwest::get(format!("{}?jql={}", jira_url, query))?
        .json::<Value>()?;

    if let Some(results) = response["issues"].as_array() {
        for issue in results {
            if let Ok(issue_data) = serde_json::from_str(&issue.to_string()) {
                println!("Issue: {}", issue_data.key);
                println!("Summary: {}", issue_data.fields.summary);
                println!("Status: {}", issue_data.fields.status.name);
            }
        }
    } else {
        println!("No issues found.");
    }

    Ok(())
}