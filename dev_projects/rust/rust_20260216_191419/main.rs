use reqwest;
use serde_json::Value;

// Define a struct to represent a Jira issue
#[derive(Debug, Serialize)]
struct Issue {
    key: String,
    summary: String,
    description: String,
}

// Function to create an issue in Jira
async fn create_issue(issue: &Issue) -> Result<(), reqwest::Error> {
    let client = reqwest::Client::new();
    let url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let response = client.post(url)
        .json(issue)
        .send().await?;
    Ok(())
}

// Function to get all issues from Jira
async fn get_issues() -> Result<Vec<Issue>, reqwest::Error> {
    let client = reqwest::Client::new();
    let url = "https://your-jira-instance.atlassian.net/rest/api/2/search";
    let response = client.get(url)
        .send().await?;
    let data: Value = serde_json::from_str(&response.text().await?)?;
    let issues: Vec<Issue> = data["issues"].as_array().unwrap()
        .iter().map(|issue| issue.as_object().unwrap())
        .map(|issue| Issue {
            key: issue["key"].as_str().unwrap().to_string(),
            summary: issue["fields"]["summary"].as_str().unwrap().to_string(),
            description: issue["fields"]["description"].as_str().unwrap().to_string(),
        })
        .collect();
    Ok(issues)
}

// Main function to run the application
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create an issue
    let issue = Issue {
        key: "RUST-123".to_string(),
        summary: "Implement Rust Agent with Jira tracking",
        description: "This is a test issue for the Rust Agent with Jira integration.",
    };
    create_issue(&issue).await?;

    // Get all issues
    let issues = get_issues().await?;
    println!("Issues in Jira:");
    for issue in issues {
        println!("{:?}", issue);
    }

    Ok(())
}