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

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let issue_key = "ABC-123";
    match fetch_jira_issue(issue_key) {
        Ok(issue) => println!("JIRA Issue: {:?}", issue),
        Err(err) => eprintln!("Error fetching JIRA issue: {}", err),
    }

    Ok(())
}