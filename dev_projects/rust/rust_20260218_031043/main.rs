use reqwest;
use serde_json;

// Define a struct to represent an issue in Jira
struct Issue {
    key: String,
    summary: String,
    status: String,
}

// Function to fetch issues from Jira
async fn fetch_issues(token: &str, project_key: &str) -> Result<Vec<Issue>, reqwest::Error> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/3/search?jql=project={} AND status!=closed", project_key);
    let response = reqwest::get(&url).await?;
    let body: serde_json::Value = response.json().await?;

    let issues: Vec<Issue> = body["issues"].as_array().unwrap()
        .iter()
        .map(|issue| {
            Issue {
                key: issue["key"].as_str().unwrap().to_string(),
                summary: issue["fields"]["summary"].as_str().unwrap().to_string(),
                status: issue["fields"]["status"]["name"].as_str().unwrap().to_string(),
            }
        })
        .collect();

    Ok(issues)
}

// Function to register an event in Jira
async fn register_event(token: &str, project_key: &str, summary: &str) -> Result<(), reqwest::Error> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/3/issue/{}/comment", project_key);
    let body = serde_json::json!({
        "body": summary,
        "update": {
            "fields": {
                "status": {
                    "name": "In Progress"
                }
            }
        }
    });

    reqwest::post(&url)
        .header("Authorization", format!("Basic {}", base64::encode(format!("{}:{}", token, "your-jira-password"))))
        .json(&body)
        .await?;

    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let token = "your-jira-token";
    let project_key = "YOUR-JIRA-PROJECT-KEY";

    // Fetch issues from Jira
    let issues = fetch_issues(token, project_key).await?;

    println!("Issues in Jira:");
    for issue in &issues {
        println!("Key: {}, Summary: {}, Status: {}", issue.key, issue.summary, issue.status);
    }

    // Register an event in Jira
    register_event(token, project_key, "New feature implemented").await?;

    Ok(())
}