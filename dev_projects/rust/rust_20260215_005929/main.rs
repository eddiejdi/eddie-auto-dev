use reqwest;
use serde_json::Value;

// Define a struct to represent a Jira issue
#[derive(Debug, Deserialize)]
struct Issue {
    key: String,
    summary: String,
    status: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Set up the Jira API endpoint
    let url = "https://your-jira-instance.atlassian.net/rest/api/2/search";
    let auth_token = "your-auth-token";

    // Create a client to make requests to the Jira API
    let mut client = reqwest::Client::new();

    // Define the query parameters for the search request
    let params = serde_urlencoded::to_string(&serde_json!({
        "jql": "project = 'Your Project' AND status = 'In Progress'",
        "fields": ["key", "summary", "status"]
    }))?;

    // Make a GET request to the Jira API
    let response = client.get(url)
        .header("Authorization", format!("Basic {}", auth_token))
        .query(&params)
        .send()?;

    // Check if the request was successful
    if response.status().is_success() {
        // Parse the JSON response into a vector of Issue structs
        let issues: Vec<Issue> = response.json()?;

        // Print out the details of each issue
        for issue in issues {
            println!("Key: {}", issue.key);
            println!("Summary: {}", issue.summary);
            println!("Status: {}", issue.status);
            println!();
        }
    } else {
        eprintln!("Failed to retrieve issues: {}", response.text()?);
    }

    Ok(())
}