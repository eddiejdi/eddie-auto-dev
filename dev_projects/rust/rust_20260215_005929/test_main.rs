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

// Test case for successful GET request
#[test]
fn test_get_issues_success() {
    // Mock the HTTP client and response
    let mut mock = reqwest::Mock::new();
    mock.get("https://your-jira-instance.atlassian.net/rest/api/2/search")
        .with_status(200)
        .body(include_str!("path/to/response.json"))
        .create();

    // Execute the main function with the mocked client
    let result = main();

    // Check if the test passed
    assert!(result.is_ok());
}

// Test case for unsuccessful GET request
#[test]
fn test_get_issues_failure() {
    // Mock the HTTP client and response
    let mut mock = reqwest::Mock::new();
    mock.get("https://your-jira-instance.atlassian.net/rest/api/2/search")
        .with_status(401)
        .create();

    // Execute the main function with the mocked client
    let result = main();

    // Check if the test passed
    assert!(result.is_err());
}

// Test case for invalid JSON response
#[test]
fn test_get_issues_invalid_json() {
    // Mock the HTTP client and response
    let mut mock = reqwest::Mock::new();
    mock.get("https://your-jira-instance.atlassian.net/rest/api/2/search")
        .with_status(200)
        .body(include_str!("path/to/invalid_response.json"))
        .create();

    // Execute the main function with the mocked client
    let result = main();

    // Check if the test passed
    assert!(result.is_err());
}

// Test case for missing fields in JSON response
#[test]
fn test_get_issues_missing_fields() {
    // Mock the HTTP client and response
    let mut mock = reqwest::Mock::new();
    mock.get("https://your-jira-instance.atlassian.net/rest/api/2/search")
        .with_status(200)
        .body(include_str!("path/to/missing_fields_response.json"))
        .create();

    // Execute the main function with the mocked client
    let result = main();

    // Check if the test passed
    assert!(result.is_err());
}