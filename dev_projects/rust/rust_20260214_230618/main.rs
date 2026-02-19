use reqwest;
use serde_json::Value;

// Define a struct to represent a Jira issue
#[derive(Debug)]
struct Issue {
    key: String,
    summary: String,
    status: String,
}

// Function to fetch issues from Jira
async fn fetch_issues(token: &str, project_key: &str) -> Result<Vec<Issue>, reqwest::Error> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/search?jql=project={}&fields=key,summary,status", project_key);
    let response = reqwest::get(&url).await?;
    let json: Value = response.json().await?;

    if json["errorMessages"].is_array() {
        return Err(reqwest::Error::from(json["errorMessages"][0]["message"]));
    }

    let issues: Vec<Issue> = json["issues"]
        .as_array()
        .ok_or_else(|| reqwest::Error::from("Invalid JSON format"))?
        .iter()
        .map(|issue| {
            Ok(Issue {
                key: issue["key"].as_str().unwrap().to_string(),
                summary: issue["fields"]["summary"].as_str().unwrap().to_string(),
                status: issue["fields"]["status"]["name"].as_str().unwrap().to_string(),
            })
        })
        .collect();

    Ok(issues)
}

// Main function to run the program
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let token = "your-jira-token";
    let project_key = "YOUR-JIRA-PROJECT-Key";

    // Fetch issues from Jira
    let issues = fetch_issues(token, project_key).await?;

    // Print the fetched issues
    for issue in &issues {
        println!("Key: {}, Summary: {}, Status: {}", issue.key, issue.summary, issue.status);
    }

    Ok(())
}